"""Unit tests for the deterministic safety rules and questionnaire branching (no database)."""
import datetime as dt
import unittest

from app.clinical import engine, safety
from app.clinical.definitions import LUMBAR_QUESTIONS, SAFETY_QUESTIONS


def ans(**kw):
    out = {}
    for k, v in kw.items():
        if v in ("UNKNOWN", "NOT_ASKED", "NOT_APPLICABLE"):
            out[k] = {"status": v, "value": None}
        else:
            out[k] = {"status": "ANSWERED", "value": v}
    return out


def all_no(**over):
    base = {q["code"]: "NO" for q in SAFETY_QUESTIONS}
    base.update(over)
    return ans(**base)


P = {"sex": "M", "birth_date": "1980-01-01"}


class SafetyRules(unittest.TestCase):
    def test_all_no_gives_no_flags(self):
        r = safety.evaluate(all_no(), {}, P)
        self.assertEqual(r["status"], "NO_FLAGS_REPORTED")
        self.assertTrue(r["complete"])

    def test_nothing_answered_is_not_confirmed(self):
        self.assertEqual(safety.evaluate({}, {}, P)["status"], "NOT_CONFIRMED")

    def test_unknown_is_missing_not_no(self):
        r = safety.evaluate(all_no(SF_URINARY_RETENTION="UNKNOWN"), {}, P)
        self.assertEqual(r["status"], "INCOMPLETE")
        self.assertEqual([m["code"] for m in r["missing"]], ["SF_URINARY_RETENTION"])

    def test_each_ces_sign_is_emergency(self):
        for code in ("SF_URINARY_RETENTION", "SF_BLADDER_BOWEL_CONTROL", "SF_SADDLE_NUMBNESS"):
            r = safety.evaluate(all_no(**{code: "YES"}), {}, P)
            self.assertEqual(r["status"], "EMERGENCY", code)
            self.assertIn("PROVOCATIVE_TESTS_BLOCKED", r["flags"])
            self.assertEqual(r["triggered"][0]["because"][0]["code"], code)

    def test_emergency_even_when_incomplete(self):
        r = safety.evaluate(ans(SF_CHEST_PAIN="YES"), {}, P)
        self.assertEqual(r["status"], "EMERGENCY")
        self.assertTrue(r["missing"])

    def test_single_review_flag_is_review_not_diagnosis(self):
        r = safety.evaluate(all_no(SF_NIGHT_PAIN="YES"), {}, P)
        self.assertEqual(r["status"], "NEEDS_REVIEW")
        self.assertEqual(r["triggered"][0]["severity"], "REVIEW")

    def test_cancer_plus_weight_loss_is_urgent(self):
        r = safety.evaluate(all_no(SF_CANCER_HISTORY="YES", SF_WEIGHT_LOSS="YES"), {}, P)
        self.assertIn("COMBO:MALIGNANCY", [t["rule"] for t in r["triggered"]])

    def test_trauma_with_osteoporosis_flags_fracture(self):
        r = safety.evaluate(all_no(SF_SIGNIFICANT_TRAUMA="YES"), ans(HX_COND_OSTEOPOROSIS="YES"), P)
        self.assertIn("SUSPECTED_FRACTURE", r["flags"])
        self.assertIn("COMBO:TRAUMA_FRAGILITY", [t["rule"] for t in r["triggered"]])
        r2 = safety.evaluate(dict(all_no(SF_SIGNIFICANT_TRAUMA="YES"), **ans(LB_FRACTURE_EXCLUDED="YES_DOCUMENTED")),
                             ans(HX_COND_OSTEOPOROSIS="YES"), P)
        self.assertNotIn("SUSPECTED_FRACTURE", r2["flags"])

    def test_age_based_fragility(self):
        old = {"sex": "F", "birth_date": (dt.date.today() - dt.timedelta(days=365 * 70)).isoformat()}
        r = safety.evaluate(all_no(SF_SIGNIFICANT_TRAUMA="YES"), ans(HX_PREGNANCY="NO"), old)
        self.assertIn("COMBO:TRAUMA_FRAGILITY", [t["rule"] for t in r["triggered"]])

    def test_patient_prior_yes_needs_confirmation_and_note(self):
        hist = ans(HX_SF_SADDLE_NUMBNESS="YES")
        r = safety.evaluate(all_no(), hist, P)
        self.assertIn("SF_SADDLE_NUMBNESS", [m["code"] for m in r["missing"]])  # NO contradicts without note
        lum = all_no()
        lum["SF_SADDLE_NUMBNESS"]["note"] = "أوضح المريض أنه خدر قديم بعد حقنة وزال"
        r2 = safety.evaluate(lum, hist, P)
        self.assertEqual(r2["status"], "NO_FLAGS_REPORTED")

    def test_surgery_without_instructions_flags(self):
        r = safety.evaluate(dict(all_no(), **ans(LB_SPINE_SURGERY="YES", LB_SURG_INSTRUCTIONS="NOT_AVAILABLE")), {}, P)
        self.assertIn("SURGICAL_RESTRICTIONS_UNCLEAR", r["flags"])

    def test_device_precaution_flags(self):
        r = safety.evaluate(all_no(), ans(HX_IMPLANTS=["PACEMAKER"], HX_MED_CLASSES=["ANTICOAGULANTS"]), P)
        self.assertIn("ACTIVE_IMPLANT", r["flags"])
        self.assertIn("ANTICOAGULANT", r["flags"])
        # pregnancy unknown for a woman is a precaution, never assumed "no"
        r2 = safety.evaluate(all_no(), {}, {"sex": "F", "birth_date": "1990-01-01"})
        self.assertIn("PREGNANCY_POSSIBLE", r2["flags"])

    def test_rapid_neuro_worsening_is_emergency(self):
        r = safety.evaluate(dict(all_no(), **ans(LB_NEURO_CHANGE="WORSE_FAST")), {}, P)
        self.assertEqual(r["status"], "EMERGENCY")


class Branching(unittest.TestCase):
    Q = [dict(q) for q in LUMBAR_QUESTIONS]

    def vis(self, a, sex="M"):
        return engine.visible_codes(self.Q, a, {"sex": sex})

    def test_leg_distribution_opens_neuro_branch(self):
        self.assertNotIn("LB_NEURO_DISTRIBUTION", self.vis(ans(LB_DISTRIBUTION="BACK_ONLY", LB_NEURO_SYMPTOMS=["NONE"])))
        self.assertIn("LB_NEURO_DISTRIBUTION", self.vis(ans(LB_DISTRIBUTION="BELOW_KNEE")))
        self.assertIn("LB_DISTRIBUTION_SIDE", self.vis(ans(LB_DISTRIBUTION="THIGH")))

    def test_distribution_defaults_to_not_asked(self):
        miss = engine.completeness(self.Q, {}, {"sex": "M"})
        self.assertIn("LB_DISTRIBUTION", [m["code"] for m in miss])

    def test_standing_walking_branch(self):
        v = self.vis(ans(LB_AGG=["WALKING"], LB_EASE=["SITTING"]))
        self.assertIn("LB_NC_RELIEF_POSITION", v)
        self.assertIn("LB_VASC_RISK", v)
        self.assertNotIn("LB_NC_RELIEF_POSITION", self.vis(ans(LB_AGG=["WALKING"], LB_EASE=["LYING"])))

    def test_surgery_and_trauma_branches(self):
        self.assertIn("LB_SURG_INSTRUCTIONS", self.vis(ans(LB_ONSET_MODE="AFTER_SURGERY")))
        self.assertIn("LB_SURG_RESTRICTIONS", self.vis(ans(LB_SPINE_SURGERY="YES", LB_SURG_INSTRUCTIONS="DOCUMENTED")))
        self.assertIn("LB_FRACTURE_EXCLUDED", self.vis(ans(SF_SIGNIFICANT_TRAUMA="YES")))

    def test_validation(self):
        q = {c["code"]: c for c in self.Q}
        with self.assertRaises(Exception):
            engine.normalize_value(q["LB_PAIN_NOW"], "ANSWERED", 11)
        with self.assertRaises(Exception):
            engine.normalize_value(q["LB_NEURO_SYMPTOMS"], "ANSWERED", ["NONE", "WEAKNESS"])
        with self.assertRaises(Exception):
            engine.normalize_value(q["LB_PAIN_NOW"], "NOT_APPLICABLE", None)
        self.assertEqual(engine.normalize_value(q["SF_FEVER"], "UNKNOWN", "YES"), None)


if __name__ == "__main__":
    unittest.main()
