"""Deterministic safety screening rules for the lumbar pathway (no ML / LLM involvement).

evaluate(...) returns a dict:
  status:    NOT_CONFIRMED | INCOMPLETE | EMERGENCY | NEEDS_REVIEW | NO_FLAGS_REPORTED
  complete:  bool — every mandatory safety question has an explicit YES/NO
  triggered: [{rule, severity, message, action, because:[{code,text,answer}]}]
  missing:   [{code, text, reason}]
  flags:     [str] — machine flags used elsewhere (test gating, plan checks, device precautions)

Principles (see docs/clinical-rules.md):
  * Empty / UNKNOWN / NOT_ASKED never counts as "No".
  * A patient's earlier "Yes" on the pre-assessment form must be explicitly re-confirmed;
    a clinician "No" that contradicts it requires an explanatory note.
  * NO_FLAGS_REPORTED allows the assessment to continue; it is NOT clearance for every
    procedure or device.
"""
from __future__ import annotations

import datetime as dt

from .definitions import SAFETY_QUESTIONS

RULES_VERSION = "lumbar-safety-2026.10-v1"

SEVERITY_ORDER = {"EMERGENCY": 3, "URGENT": 2, "REVIEW": 1}

GROUP_MESSAGES = {
    "CES": ("اشتباه بأعراض متلازمة ذيل الفرس (Cauda Equina): إيقاف الفحص الاستفزازي والعلاج الروتيني، وإحالة طبية إسعافية فورية "
            "وتوثيق من اتخذ القرار ومتى."),
    "NEURO": "عجز عصبي جديد أو سريع التفاقم أو اضطراب عصبي مفاجئ: إيقاف المسار الروتيني وإحالة طبية عاجلة.",
    "CARDIO": "أعراض صدرية/قلبية/وعائية حادة محتملة: لا يُجرى أي فحص أو علاج، وتوجيه فوري لتقييم طبي إسعافي.",
}

TIER_ACTIONS = {
    "EMERGENCY": "إحالة طبية إسعافية — تعليق الفحص الاستفزازي والعلاج",
    "URGENT": "تقييم طبي في اليوم نفسه/قريب قبل بدء العلاج",
    "REVIEW": "مراجعة سريرية واستيضاح قبل اعتماد الخطة",
}

ACTIVE_IMPLANTS = {"PACEMAKER", "ICD", "NEUROSTIMULATOR", "PUMP", "COCHLEAR"}
METAL_IMPLANTS = {"JOINT", "PLATES", "SPINE_IMPLANT"}

FLAG_LABELS = {
    "PROVOCATIVE_TESTS_BLOCKED": "الاختبارات الاستفزازية محجوبة",
    "SUSPECTED_FRACTURE": "احتمال كسر غير مستبعد — تُحجب الاختبارات التحميلية",
    "SURGICAL_RESTRICTIONS_UNCLEAR": "قيود الجراحة غير موثقة — لا يمكن إرسال الخطة",
    "ACTIVE_IMPLANT": "جهاز إلكتروني/نشط مزروع",
    "METAL_IMPLANT": "معادن/زرعات داخل الجسم",
    "PREGNANCY_POSSIBLE": "حمل حالي أو محتمل",
    "MALIGNANCY_HISTORY": "تاريخ سرطان",
    "REDUCED_SENSATION": "نقص إحساس مُبلّغ أو مُكتشف",
    "ANTICOAGULANT": "يتناول مميعات دم",
    "EPILEPSY": "صرع/اختلاج",
    "DIABETES": "سكري",
    "STEROIDS": "ستيرويدات",
    "OSTEOPOROSIS": "هشاشة عظام",
}

# precaution flags shown on every DEVICE plan item (reminder to check manufacturer documentation)
DEVICE_PRECAUTION_FLAGS = ["ACTIVE_IMPLANT", "METAL_IMPLANT", "PREGNANCY_POSSIBLE", "MALIGNANCY_HISTORY",
                           "REDUCED_SENSATION", "ANTICOAGULANT", "EPILEPSY", "DIABETES"]


def _a(answers, code):
    return answers.get(code) or {"status": "NOT_ASKED"}


def _yes(answers, code):
    a = _a(answers, code)
    return a["status"] == "ANSWERED" and a.get("value") == "YES"


def _includes(answers, code, val):
    a = _a(answers, code)
    return a["status"] == "ANSWERED" and isinstance(a.get("value"), list) and val in a["value"]


def _eq(answers, code, val):
    a = _a(answers, code)
    return a["status"] == "ANSWERED" and a.get("value") == val


def age_on(birth_date, today=None):
    if not birth_date:
        return None
    if isinstance(birth_date, str):
        birth_date = dt.date.fromisoformat(birth_date)
    today = today or dt.date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def evaluate(lumbar: dict, history: dict, patient: dict, exam_results=None, today=None) -> dict:
    triggered, missing, flags = [], [], set()
    sq_by_code = {q["code"]: q for q in SAFETY_QUESTIONS}
    age = age_on(patient.get("birth_date"), today)
    any_answered = False

    def because(*codes):
        out = []
        for c in codes:
            a = lumbar.get(c) or history.get(c) or {"status": "NOT_ASKED"}
            q = sq_by_code.get(c)
            out.append({"code": c, "text": q["text"] if q else c,
                        "answer": "نعم" if a.get("value") == "YES" else (a.get("value") if a["status"] == "ANSWERED" else a["status"])})
        return out

    def trig(rule, severity, message, codes):
        triggered.append({"rule": rule, "severity": severity, "message": message,
                          "action": TIER_ACTIONS[severity], "because": because(*codes)})

    # 1) mandatory safety questions: completeness + per-question tiers
    for q in SAFETY_QUESTIONS:
        a = _a(lumbar, q["code"])
        if a["status"] == "NOT_APPLICABLE" and q.get("allow_na"):
            any_answered = True
            continue
        if a["status"] != "ANSWERED":
            reason = "لم يُسأل" if a["status"] == "NOT_ASKED" else "الإجابة «غير معروف» — يجب حسمها"
            hc = q.get("history_code")
            if hc and _yes(history, hc):
                reason += " (أجاب المريض «نعم» في الاستبيان المسبق)"
            missing.append({"code": q["code"], "text": q["text"], "reason": reason})
            continue
        any_answered = True
        hc = q.get("history_code")
        if a["value"] == "NO" and hc and _yes(history, hc) and not (a.get("note") or "").strip():
            missing.append({"code": q["code"], "text": q["text"],
                            "reason": "تعارض: المريض أجاب «نعم» مسبقاً والمعالج سجّل «لا» دون ملاحظة توضيحية"})
        if a["value"] == "YES":
            tier = q["tier"]
            if tier == "EMERGENCY":
                trig("SF:" + q["code"], "EMERGENCY", GROUP_MESSAGES[q["group"]], [q["code"]])
            elif tier == "URGENT":
                msg = {
                    "SF_UNILATERAL_LEG_SWELLING": "تورم/ألم حديث في ساق واحدة: يحتاج تقييماً طبياً لاستبعاد سبب وعائي قبل العلاج.",
                    "SF_SYNCOPE": "إغماء/دوار شديد حديث: يحتاج تقييماً طبياً قبل الجهد البدني.",
                    "SF_FEVER": "حمى غير مفسرة: يحتاج تقييماً طبياً لاستبعاد سبب التهابي/عدوى.",
                }.get(q["code"], q["text"])
                trig("SF:" + q["code"], "URGENT", msg, [q["code"]])
            else:
                trig("SF:" + q["code"], "REVIEW", "علامة تحتاج مراجعة سريرية واستيضاحاً: " + q["text"]
                     + " (علامة واحدة ليست تشخيصاً).", [q["code"]])

    # 2) combinations
    osteo = _yes(history, "HX_COND_OSTEOPOROSIS")
    steroids = _includes(history, "HX_MED_CLASSES", "STEROIDS")
    if osteo:
        flags.add("OSTEOPOROSIS")
    if steroids:
        flags.add("STEROIDS")
    if _yes(lumbar, "SF_SIGNIFICANT_TRAUMA") or _eq(lumbar, "LB_ONSET_MODE", "AFTER_TRAUMA"):
        if not _eq(lumbar, "LB_FRACTURE_EXCLUDED", "YES_DOCUMENTED"):
            flags.add("SUSPECTED_FRACTURE")
        if (osteo or steroids or (age is not None and age >= 65)) and not _eq(lumbar, "LB_FRACTURE_EXCLUDED", "YES_DOCUMENTED"):
            reasons = [x for x, c in (("هشاشة عظام", osteo), ("ستيرويدات", steroids),
                                      ("العمر ≥ 65", age is not None and age >= 65)) if c]
            trig("COMBO:TRAUMA_FRAGILITY", "URGENT",
                 "رضّ مع عامل هشاشة (" + "، ".join(reasons) + "): احتمال كسر أعلى، يلزم تقييم طبي/تصوير قبل أي اختبار تحميلي.",
                 ["SF_SIGNIFICANT_TRAUMA"])
    cancer = _yes(lumbar, "SF_CANCER_HISTORY") or _yes(history, "HX_COND_CANCER")
    if cancer:
        flags.add("MALIGNANCY_HISTORY")
        companions = [c for c in ("SF_NIGHT_PAIN", "SF_WEIGHT_LOSS", "SF_SYSTEMIC_UNWELL") if _yes(lumbar, c)]
        if companions or (age is not None and age >= 50 and _eq(lumbar, "LB_TREND", "WORSENING")):
            trig("COMBO:MALIGNANCY", "URGENT",
                 "تاريخ سرطان مع علامات مرافقة: يحتاج تقييماً طبياً لاستبعاد سبب غير ميكانيكي قبل العلاج.",
                 ["SF_CANCER_HISTORY"] + companions)
    if _yes(lumbar, "SF_FEVER") and _yes(lumbar, "SF_INFECTION_RISK"):
        trig("COMBO:INFECTION", "URGENT", "حمى مع عامل خطر عدوى: إحالة طبية قبل العلاج.", ["SF_FEVER", "SF_INFECTION_RISK"])
    if _yes(lumbar, "SF_BILATERAL_LEG_SYMPTOMS") and _yes(lumbar, "SF_SEXUAL_DYSFUNCTION_NEW"):
        trig("COMBO:CES_PARTIAL", "URGENT",
             "أعراض بالساقين معاً مع تغير وظيفي حديث: استيضاح فوري لأعراض ذيل الفرس وتقييم طبي عاجل.",
             ["SF_BILATERAL_LEG_SYMPTOMS", "SF_SEXUAL_DYSFUNCTION_NEW"])

    # 3) branch-derived rules from the lumbar assessment
    if _eq(lumbar, "LB_NEURO_CHANGE", "WORSE_FAST"):
        trig("LB:NEURO_RAPID", "EMERGENCY", GROUP_MESSAGES["NEURO"], ["LB_NEURO_CHANGE"])
    if _includes(lumbar, "LB_SURG_COMPLICATIONS", "NEW_DEFICIT"):
        trig("LB:POSTOP_DEFICIT", "URGENT", "عجز عصبي جديد بعد الجراحة: تواصل مع الفريق الجراحي قبل أي علاج.",
             ["LB_SURG_COMPLICATIONS"])
    if _includes(lumbar, "LB_SURG_COMPLICATIONS", "WOUND") or _includes(lumbar, "LB_SURG_COMPLICATIONS", "FEVER"):
        trig("LB:POSTOP_INFECTION", "URGENT", "علامات محتملة لمضاعفات الجرح/عدوى بعد الجراحة: تقييم طبي قبل العلاج.",
             ["LB_SURG_COMPLICATIONS"])
    surgery_branch = _yes(lumbar, "LB_SPINE_SURGERY") or _eq(lumbar, "LB_ONSET_MODE", "AFTER_SURGERY")
    if surgery_branch and not (_eq(lumbar, "LB_SURG_INSTRUCTIONS", "DOCUMENTED") or _eq(lumbar, "LB_SURG_INSTRUCTIONS", "NONE_GIVEN")):
        flags.add("SURGICAL_RESTRICTIONS_UNCLEAR")

    # 4) precaution flags (reminders, not automatic contraindications)
    imp = _a(history, "HX_IMPLANTS")
    if imp["status"] == "ANSWERED":
        v = set(imp["value"])
        if v & ACTIVE_IMPLANTS:
            flags.add("ACTIVE_IMPLANT")
        if v & METAL_IMPLANTS:
            flags.add("METAL_IMPLANT")
    if patient.get("sex") == "F":
        p = _a(history, "HX_PREGNANCY")
        if p["status"] in ("UNKNOWN", "NOT_ASKED") or (p["status"] == "ANSWERED" and p["value"] in ("YES", "UNSURE")):
            flags.add("PREGNANCY_POSSIBLE")
    if _includes(lumbar, "LB_NEURO_SYMPTOMS", "NUMBNESS"):
        flags.add("REDUCED_SENSATION")
    for r in exam_results or []:
        if r.get("test_code", "").startswith("NEURO_DERM") and r.get("value_text") in ("REDUCED", "ABSENT"):
            flags.add("REDUCED_SENSATION")
    if _includes(history, "HX_MED_CLASSES", "ANTICOAGULANTS"):
        flags.add("ANTICOAGULANT")
    if _yes(history, "HX_COND_EPILEPSY"):
        flags.add("EPILEPSY")
    if _yes(history, "HX_COND_DIABETES"):
        flags.add("DIABETES")

    # 5) status
    worst = max((SEVERITY_ORDER[t["severity"]] for t in triggered), default=0)
    if worst == 3:
        status = "EMERGENCY"
        flags.add("PROVOCATIVE_TESTS_BLOCKED")
    elif worst >= 1:
        status = "NEEDS_REVIEW"
    elif not any_answered:
        status = "NOT_CONFIRMED"
    elif missing:
        status = "INCOMPLETE"
    else:
        status = "NO_FLAGS_REPORTED"
    triggered.sort(key=lambda t: -SEVERITY_ORDER[t["severity"]])
    return {
        "status": status,
        "complete": not missing,
        "triggered": triggered,
        "missing": missing,
        "flags": sorted(flags),
        "rules_version": RULES_VERSION,
    }


STATUS_LABELS = {
    "NOT_CONFIRMED": "لم يتأكد بعد",
    "INCOMPLETE": "غير مكتمل",
    "EMERGENCY": "مسار إسعافي — إحالة فورية",
    "NEEDS_REVIEW": "يحتاج مراجعة/تقييم إضافي",
    "NO_FLAGS_REPORTED": "لا توجد مؤشرات مبلّغ عنها",
}
