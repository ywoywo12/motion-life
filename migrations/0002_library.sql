-- Exercise library + device built-in programs on plan items
ALTER TABLE catalogs DROP CONSTRAINT catalogs_kind_check;
ALTER TABLE catalogs ADD CONSTRAINT catalogs_kind_check CHECK (kind IN ('TEST','EQUIPMENT','INTERVENTION','OUTCOME','EXERCISE'));
ALTER TABLE plan_items ADD COLUMN exercise_code text;
ALTER TABLE plan_items ADD COLUMN program_code text;
ALTER TABLE plan_items ADD COLUMN program_label text;
