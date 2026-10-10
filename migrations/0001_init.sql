-- Motion Life Clinical System — initial schema (V1)
-- All clinical identifiers are random UUIDs. Times are timestamptz (UTC).

-- gen_random_uuid() is built into PostgreSQL 13+

-- ───────────── Organisation, users, RBAC ─────────────
CREATE TABLE departments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code        text NOT NULL UNIQUE,            -- MEN / WOMEN
  name        text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE roles (
  code        text PRIMARY KEY,                -- DIRECTOR, DEPT_HEAD, ...
  name        text NOT NULL
);

CREATE TABLE permissions (
  code        text PRIMARY KEY,
  description text NOT NULL
);

CREATE TABLE role_permissions (
  role_code       text NOT NULL REFERENCES roles(code),
  permission_code text NOT NULL REFERENCES permissions(code),
  PRIMARY KEY (role_code, permission_code)
);

CREATE TABLE users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username         text NOT NULL UNIQUE CHECK (username ~ '^[a-z0-9._-]{3,40}$'),
  full_name        text NOT NULL,
  role_code        text NOT NULL REFERENCES roles(code),
  password_hash    text NOT NULL,
  is_active        boolean NOT NULL DEFAULT true,
  is_test_account  boolean NOT NULL DEFAULT false,
  must_change_password boolean NOT NULL DEFAULT false,
  failed_attempts  int NOT NULL DEFAULT 0,
  locked_until     timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  deactivated_at   timestamptz,
  version          int NOT NULL DEFAULT 1
);

CREATE TABLE memberships (
  user_id       uuid NOT NULL REFERENCES users(id),
  department_id uuid NOT NULL REFERENCES departments(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, department_id)
);

CREATE TABLE review_delegations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delegator_id  uuid NOT NULL REFERENCES users(id),
  delegate_id   uuid NOT NULL REFERENCES users(id),
  department_id uuid NOT NULL REFERENCES departments(id),
  reason        text NOT NULL,
  granted_at    timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz,
  revoked_at    timestamptz,
  revoked_by    uuid REFERENCES users(id),
  CHECK (delegator_id <> delegate_id)
);
CREATE INDEX ON review_delegations (delegate_id) WHERE revoked_at IS NULL;

CREATE TABLE auth_sessions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash    text NOT NULL UNIQUE,
  csrf_token    text NOT NULL,
  user_id       uuid NOT NULL REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL,
  revoked_at    timestamptz,
  ip            text,
  user_agent    text
);
CREATE INDEX ON auth_sessions (user_id);

CREATE TABLE login_attempts (
  id          bigserial PRIMARY KEY,
  username    text,
  ip          text,
  success     boolean NOT NULL,
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON login_attempts (ip, at);

-- ───────────── Patients and episodes ─────────────
CREATE SEQUENCE patient_file_seq START 1;

CREATE TABLE patients (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  file_no          text NOT NULL UNIQUE,
  serial_no        text,
  archive_shelf    text,
  archive_cabinet  text,
  full_name        text NOT NULL CHECK (length(full_name) BETWEEN 2 AND 200),
  name_normalized  text NOT NULL,
  birth_date       date,
  sex              text NOT NULL CHECK (sex IN ('M','F')),
  phone            text,
  phone_normalized text,
  occupation       text,
  height_cm        numeric(5,1) CHECK (height_cm IS NULL OR height_cm BETWEEN 40 AND 250),
  weight_kg        numeric(5,1) CHECK (weight_kg IS NULL OR weight_kg BETWEEN 2 AND 400),
  referring_doctor text,
  department_id    uuid NOT NULL REFERENCES departments(id),
  is_synthetic     boolean NOT NULL DEFAULT false,
  created_by       uuid NOT NULL REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  version          int NOT NULL DEFAULT 1
);
CREATE INDEX ON patients (department_id);
CREATE INDEX ON patients (name_normalized);
CREATE INDEX ON patients (phone_normalized);

CREATE TABLE patient_contacts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id   uuid NOT NULL REFERENCES patients(id),
  name         text NOT NULL,
  relation     text,
  phone        text,
  is_emergency boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON patient_contacts (patient_id);

CREATE TABLE patient_assignments (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id   uuid NOT NULL REFERENCES patients(id),
  therapist_id uuid NOT NULL REFERENCES users(id),
  assigned_by  uuid NOT NULL REFERENCES users(id),
  assigned_at  timestamptz NOT NULL DEFAULT now(),
  ended_at     timestamptz,
  ended_by     uuid REFERENCES users(id),
  reason       text
);
CREATE UNIQUE INDEX patient_assignments_active ON patient_assignments (patient_id, therapist_id) WHERE ended_at IS NULL;
CREATE INDEX ON patient_assignments (therapist_id) WHERE ended_at IS NULL;

CREATE TABLE department_transfers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id    uuid NOT NULL REFERENCES patients(id),
  from_department_id uuid NOT NULL REFERENCES departments(id),
  to_department_id   uuid NOT NULL REFERENCES departments(id),
  reason        text NOT NULL,
  transferred_by uuid NOT NULL REFERENCES users(id),
  at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical_episodes (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id   uuid NOT NULL REFERENCES patients(id),
  region       text NOT NULL CHECK (region IN ('LUMBAR')),
  title        text NOT NULL,
  status       text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ON_HOLD','CLOSED')),
  hold_reason  text,
  created_by   uuid NOT NULL REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  closed_at    timestamptz,
  version      int NOT NULL DEFAULT 1
);
CREATE INDEX ON clinical_episodes (patient_id);

-- ───────────── Questionnaire engine ─────────────
CREATE TABLE questionnaires (
  id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code   text NOT NULL UNIQUE,      -- MEDICAL_HISTORY, LUMBAR_ASSESSMENT
  name   text NOT NULL
);

CREATE TABLE questionnaire_versions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  questionnaire_id uuid NOT NULL REFERENCES questionnaires(id),
  version          int NOT NULL,
  status           text NOT NULL CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
  definition       jsonb NOT NULL,        -- sections/order metadata
  content_hash     text NOT NULL,
  published_at     timestamptz,
  published_by     uuid REFERENCES users(id),
  UNIQUE (questionnaire_id, version)
);

-- Immutable once published: the exact text/options a patient answered are preserved.
CREATE TABLE question_definitions (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  questionnaire_version_id uuid NOT NULL REFERENCES questionnaire_versions(id),
  code                     text NOT NULL,
  section                  text NOT NULL,
  position                 int NOT NULL,
  definition               jsonb NOT NULL,   -- text, type, options, show_if, safety flags
  UNIQUE (questionnaire_version_id, code)
);

-- One row per recorded value; older values are kept (superseded_at) for history.
CREATE TABLE answers (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id             uuid NOT NULL REFERENCES patients(id),
  episode_id             uuid REFERENCES clinical_episodes(id),
  question_definition_id uuid NOT NULL REFERENCES question_definitions(id),
  question_code          text NOT NULL,
  status                 text NOT NULL CHECK (status IN ('ANSWERED','UNKNOWN','NOT_ASKED','NOT_APPLICABLE')),
  value                  jsonb,
  source                 text NOT NULL CHECK (source IN ('PATIENT_REPORTED','RECEPTION_ENTRY','THERAPIST_ENTRY','CLINICIAN_OBSERVED')),
  note                   text,
  recorded_by            uuid NOT NULL REFERENCES users(id),
  recorded_at            timestamptz NOT NULL DEFAULT now(),
  superseded_at          timestamptz,
  superseded_by          uuid REFERENCES answers(id)
);
-- exactly one current answer per (patient, scope, question)
CREATE UNIQUE INDEX answers_current ON answers (patient_id, COALESCE(episode_id, '00000000-0000-0000-0000-000000000000'::uuid), question_code)
  WHERE superseded_at IS NULL;
CREATE INDEX ON answers (episode_id);

CREATE TABLE medical_history_entries (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id   uuid NOT NULL REFERENCES patients(id),
  entry_type   text NOT NULL CHECK (entry_type IN ('SURGERY','MEDICATION')),
  data         jsonb NOT NULL,
  created_by   uuid NOT NULL REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  removed_at   timestamptz,
  removed_by   uuid REFERENCES users(id),
  removed_reason text
);
CREATE INDEX ON medical_history_entries (patient_id);

CREATE TABLE medical_history_reviews (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id  uuid NOT NULL REFERENCES patients(id),
  reviewed_by uuid NOT NULL REFERENCES users(id),
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  note        text
);

-- ───────────── Safety ─────────────
CREATE TABLE safety_screenings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id    uuid NOT NULL REFERENCES clinical_episodes(id),
  status        text NOT NULL CHECK (status IN ('NOT_CONFIRMED','INCOMPLETE','EMERGENCY','NEEDS_REVIEW','NO_FLAGS_REPORTED')),
  triggered     jsonb NOT NULL DEFAULT '[]',
  missing       jsonb NOT NULL DEFAULT '[]',
  flags         jsonb NOT NULL DEFAULT '[]',
  rules_version text NOT NULL,
  computed_by   uuid NOT NULL REFERENCES users(id),
  computed_at   timestamptz NOT NULL DEFAULT now(),
  is_current    boolean NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX safety_current ON safety_screenings (episode_id) WHERE is_current;

CREATE TABLE alerts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id  uuid NOT NULL REFERENCES patients(id),
  episode_id  uuid REFERENCES clinical_episodes(id),
  severity    text NOT NULL CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','INFO')),
  code        text NOT NULL,
  message     text NOT NULL,
  details     jsonb NOT NULL DEFAULT '{}',
  status      text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
CREATE UNIQUE INDEX alerts_open_unique ON alerts (episode_id, code) WHERE status <> 'RESOLVED';
CREATE INDEX ON alerts (patient_id);

CREATE TABLE alert_acknowledgments (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id  uuid NOT NULL REFERENCES alerts(id),
  user_id   uuid NOT NULL REFERENCES users(id),
  note      text NOT NULL CHECK (length(note) >= 3),
  at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE referrals (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id   uuid NOT NULL REFERENCES clinical_episodes(id),
  urgency      text NOT NULL CHECK (urgency IN ('EMERGENCY','URGENT','ROUTINE')),
  destination  text NOT NULL,
  reason       text NOT NULL,
  patient_informed boolean NOT NULL DEFAULT false,
  decided_by   uuid NOT NULL REFERENCES users(id),
  decided_at   timestamptz NOT NULL DEFAULT now()
);

-- ───────────── Assessment ─────────────
CREATE TABLE assessments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id    uuid NOT NULL UNIQUE REFERENCES clinical_episodes(id),
  status        text NOT NULL DEFAULT 'IN_PROGRESS' CHECK (status IN ('IN_PROGRESS','FINALIZED')),
  current_version int NOT NULL DEFAULT 0,
  created_by    uuid NOT NULL REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  version       int NOT NULL DEFAULT 1
);

CREATE TABLE assessment_versions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id uuid NOT NULL REFERENCES assessments(id),
  version_no    int NOT NULL,
  snapshot      jsonb NOT NULL,       -- answers + exam results + safety at finalization
  note          text,
  created_by    uuid NOT NULL REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (assessment_id, version_no)
);

CREATE TABLE exam_results (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id uuid NOT NULL REFERENCES assessments(id),
  test_code     text NOT NULL,
  catalog_version int NOT NULL,
  side          text NOT NULL DEFAULT 'NA' CHECK (side IN ('LEFT','RIGHT','BILATERAL','CENTRAL','NA')),
  result        text NOT NULL CHECK (result IN ('POSITIVE','NEGATIVE','INCONCLUSIVE','NOT_DONE','RECORDED')),
  value_num     numeric,
  value_text    text,
  unit          text,
  details       jsonb NOT NULL DEFAULT '{}',
  not_done_reason text,
  notes         text,
  recorded_by   uuid NOT NULL REFERENCES users(id),
  recorded_at   timestamptz NOT NULL DEFAULT now(),
  superseded_at timestamptz,
  amended_reason text,
  CHECK (result <> 'NOT_DONE' OR (not_done_reason IS NOT NULL AND length(not_done_reason) > 1))
);
CREATE INDEX ON exam_results (assessment_id) WHERE superseded_at IS NULL;

CREATE TABLE goals (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id   uuid NOT NULL REFERENCES clinical_episodes(id),
  description  text NOT NULL,
  measure      text NOT NULL,         -- what is measured
  baseline_value text,
  target_value text NOT NULL,
  unit         text,
  target_date  date,
  status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ACHIEVED','PARTIAL','NOT_ACHIEVED','DROPPED')),
  created_by   uuid NOT NULL REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON goals (episode_id);

-- ───────────── Treatment plans ─────────────
CREATE TABLE treatment_plans (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id  uuid NOT NULL UNIQUE REFERENCES clinical_episodes(id),
  created_by  uuid NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE plan_versions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id      uuid NOT NULL REFERENCES treatment_plans(id),
  version_no   int NOT NULL,
  status       text NOT NULL CHECK (status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','ESCALATED','ON_HOLD','APPROVED','SUPERSEDED','CLOSED')),
  content      jsonb NOT NULL DEFAULT '{}',
  assessment_version_id uuid REFERENCES assessment_versions(id),
  safety_snapshot jsonb,
  based_on_version_id uuid REFERENCES plan_versions(id),
  author_id    uuid NOT NULL REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  submitted_at timestamptz,
  approved_at  timestamptz,
  approved_by  uuid REFERENCES users(id),
  lock_version int NOT NULL DEFAULT 1,
  UNIQUE (plan_id, version_no),
  CHECK (status <> 'APPROVED' OR (approved_by IS NOT NULL AND approved_by <> author_id))
);
-- at most one approved and one open (draft/in review) version per plan
CREATE UNIQUE INDEX plan_one_approved ON plan_versions (plan_id) WHERE status = 'APPROVED';
CREATE UNIQUE INDEX plan_one_open ON plan_versions (plan_id) WHERE status IN ('DRAFT','SUBMITTED','ESCALATED');

CREATE TABLE plan_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_version_id uuid NOT NULL REFERENCES plan_versions(id),
  position        int NOT NULL,
  category        text NOT NULL CHECK (category IN ('DEVICE','MANUAL','GYM','HOME','EDUCATION','OTHER')),
  title           text NOT NULL,
  equipment_code  text,
  target          text,
  dosage          text,
  method          text,
  precautions     text,
  progression_criteria text,
  stop_criteria   text,
  phase           text CHECK (phase IS NULL OR phase IN ('1','2','3','1-2','2-3','1-3')),
  contraindications_reviewed boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON plan_items (plan_version_id);

CREATE TABLE approval_decisions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_version_id uuid NOT NULL REFERENCES plan_versions(id),
  action          text NOT NULL CHECK (action IN ('SUBMIT','APPROVE','REQUEST_CHANGES','ESCALATE','HOLD','RESUME','SUPERSEDE','CLOSE','REVISE')),
  from_status     text NOT NULL,
  to_status       text NOT NULL,
  actor_id        uuid NOT NULL REFERENCES users(id),
  actor_role      text NOT NULL,
  comment         text,
  item_comments   jsonb NOT NULL DEFAULT '{}',
  at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON approval_decisions (plan_version_id);

-- ───────────── Sessions and outcomes ─────────────
CREATE TABLE sessions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id      uuid NOT NULL REFERENCES clinical_episodes(id),
  plan_version_id uuid NOT NULL REFERENCES plan_versions(id),
  session_no      int NOT NULL CHECK (session_no >= 1),
  session_date    date NOT NULL,
  therapist_id    uuid NOT NULL REFERENCES users(id),
  pain_before     int CHECK (pain_before BETWEEN 0 AND 10),
  pain_after      int CHECK (pain_after BETWEEN 0 AND 10),
  response        text,
  adverse_event   boolean NOT NULL DEFAULT false,
  adverse_details text,
  temp_modification text,
  needs_review    boolean NOT NULL DEFAULT false,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (episode_id, session_no),
  CHECK (NOT adverse_event OR (adverse_details IS NOT NULL AND length(adverse_details) > 2))
);
CREATE INDEX ON sessions (episode_id);

CREATE TABLE session_interventions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    uuid NOT NULL REFERENCES sessions(id),
  plan_item_id  uuid REFERENCES plan_items(id),
  title         text NOT NULL,
  performed     boolean NOT NULL DEFAULT true,
  dosage_actual text,
  is_deviation  boolean NOT NULL DEFAULT false,
  deviation_reason text,
  notes         text,
  CHECK (NOT is_deviation OR (deviation_reason IS NOT NULL AND length(deviation_reason) > 2))
);
CREATE INDEX ON session_interventions (session_id);

CREATE TABLE progress_reviews (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id  uuid NOT NULL REFERENCES clinical_episodes(id),
  milestone   text NOT NULL CHECK (milestone IN ('S6','S12','AD_HOC','DISCHARGE')),
  after_session_no int,
  summary     text NOT NULL,
  decision    text NOT NULL CHECK (decision IN ('CONTINUE','MODIFY_PLAN','DISCHARGE','REFER','HOLD')),
  goal_status jsonb NOT NULL DEFAULT '{}',
  created_by  uuid NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX progress_one_milestone ON progress_reviews (episode_id, milestone) WHERE milestone IN ('S6','S12','DISCHARGE');

CREATE TABLE outcome_measures (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id  uuid NOT NULL REFERENCES clinical_episodes(id),
  measure_code text NOT NULL,
  label       text,              -- e.g. activity name for PSFS items
  timepoint   text NOT NULL CHECK (timepoint IN ('BASELINE','S6','S12','DISCHARGE','OTHER')),
  value_num   numeric NOT NULL,
  unit        text,
  progress_review_id uuid REFERENCES progress_reviews(id),
  session_id  uuid REFERENCES sessions(id),
  recorded_by uuid NOT NULL REFERENCES users(id),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  superseded_at timestamptz
);
CREATE INDEX ON outcome_measures (episode_id, measure_code);

-- ───────────── Attachments ─────────────
CREATE TABLE attachments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id  uuid NOT NULL REFERENCES patients(id),
  episode_id  uuid REFERENCES clinical_episodes(id),
  kind        text NOT NULL CHECK (kind IN ('IMAGING_REPORT','SURGICAL_REPORT','REFERRAL_LETTER','OTHER')),
  filename    text NOT NULL,
  mime        text NOT NULL,
  size_bytes  int NOT NULL,
  sha256      text NOT NULL,
  storage_key text NOT NULL UNIQUE,
  uploaded_by uuid NOT NULL REFERENCES users(id),
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  removed_at  timestamptz
);
CREATE INDEX ON attachments (patient_id);

-- ───────────── Catalogs ─────────────
CREATE TABLE catalogs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind        text NOT NULL CHECK (kind IN ('TEST','EQUIPMENT','INTERVENTION','OUTCOME')),
  code        text NOT NULL,
  version     int NOT NULL,
  status      text NOT NULL CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
  data        jsonb NOT NULL,
  review_note text,
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  published_by uuid REFERENCES users(id),
  published_at timestamptz,
  UNIQUE (kind, code, version)
);
CREATE UNIQUE INDEX catalogs_one_published ON catalogs (kind, code) WHERE status = 'PUBLISHED';

CREATE TABLE protocol_versions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code        text NOT NULL,
  version     int NOT NULL,
  status      text NOT NULL CHECK (status IN ('DRAFT','UNDER_REVIEW','PUBLISHED','RETIRED')),
  title       text NOT NULL,
  content     jsonb NOT NULL,
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  reviewed_by uuid REFERENCES users(id),
  published_at timestamptz,
  UNIQUE (code, version)
);

-- ───────────── Accounting placeholders (paper file: up to 4 installments) ─────────────
CREATE TABLE billing_packages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id      uuid NOT NULL UNIQUE REFERENCES clinical_episodes(id),
  sessions_agreed int NOT NULL CHECK (sessions_agreed BETWEEN 1 AND 100),
  total_amount    numeric(14,2) NOT NULL CHECK (total_amount >= 0),
  currency        text NOT NULL DEFAULT 'SYP',
  created_by      uuid NOT NULL REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE payments (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  package_id     uuid NOT NULL REFERENCES billing_packages(id),
  installment_no int NOT NULL CHECK (installment_no BETWEEN 1 AND 4),
  amount         numeric(14,2) NOT NULL CHECK (amount > 0),
  paid_on        date NOT NULL,
  recorded_by    uuid NOT NULL REFERENCES users(id),
  recorded_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (package_id, installment_no)
);

-- ───────────── Audit (append-only) ─────────────
CREATE TABLE audit_events (
  id          bigserial PRIMARY KEY,
  at          timestamptz NOT NULL DEFAULT now(),
  actor_id    uuid REFERENCES users(id),
  actor_role  text,
  action      text NOT NULL,
  entity_type text NOT NULL,
  entity_id   text,
  patient_id  uuid,
  reason      text,
  details     jsonb NOT NULL DEFAULT '{}',
  ip          text,
  category    text NOT NULL DEFAULT 'CLINICAL' CHECK (category IN ('CLINICAL','SECURITY','ADMIN','ACCESS'))
);
CREATE INDEX ON audit_events (patient_id, at);
CREATE INDEX ON audit_events (entity_type, entity_id);
CREATE INDEX ON audit_events (at);

CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only';
END $$;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

-- Clinical records must not be hard-deleted (use superseded/removed markers).
CREATE FUNCTION forbid_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'hard delete is not allowed on %', TG_TABLE_NAME;
END $$;
CREATE TRIGGER no_delete_patients BEFORE DELETE ON patients FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER no_delete_answers BEFORE DELETE ON answers FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER no_delete_exam BEFORE DELETE ON exam_results FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER no_delete_plan_versions BEFORE DELETE ON plan_versions FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER no_delete_decisions BEFORE DELETE ON approval_decisions FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER no_delete_sessions BEFORE DELETE ON sessions FOR EACH ROW EXECUTE FUNCTION forbid_delete();
CREATE TRIGGER no_delete_assessment_versions BEFORE DELETE ON assessment_versions FOR EACH ROW EXECUTE FUNCTION forbid_delete();

-- Approved/finalised history is immutable: an approved plan version's content and items cannot change.
CREATE FUNCTION plan_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status NOT IN ('DRAFT') AND NEW.content IS DISTINCT FROM OLD.content THEN
    RAISE EXCEPTION 'plan version % content is frozen in status %', OLD.id, OLD.status;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER plan_version_frozen BEFORE UPDATE ON plan_versions FOR EACH ROW EXECUTE FUNCTION plan_version_guard();

CREATE FUNCTION plan_item_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE st text;
BEGIN
  SELECT status INTO st FROM plan_versions WHERE id = COALESCE(NEW.plan_version_id, OLD.plan_version_id);
  IF st <> 'DRAFT' THEN
    RAISE EXCEPTION 'plan items are frozen (version status %)', st;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER plan_items_frozen BEFORE INSERT OR UPDATE OR DELETE ON plan_items FOR EACH ROW EXECUTE FUNCTION plan_item_guard();

-- Sessions are immutable after creation except the review flag (corrections are new audit-tracked records).
CREATE FUNCTION session_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.plan_version_id IS DISTINCT FROM OLD.plan_version_id
     OR NEW.session_no IS DISTINCT FROM OLD.session_no
     OR NEW.episode_id IS DISTINCT FROM OLD.episode_id THEN
    RAISE EXCEPTION 'session linkage is immutable';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER session_linkage BEFORE UPDATE ON sessions FOR EACH ROW EXECUTE FUNCTION session_guard();

CREATE TABLE schema_migrations (
  name       text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
