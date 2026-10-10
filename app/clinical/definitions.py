"""Seed source for questionnaire definitions (published to the DB as version 1).

At runtime the application reads the *published version from the database*, so the
meaning of an answer stays tied to the exact question text it was recorded against.
Changing this file and re-seeding creates a NEW version; it does not rewrite old ones.

Question fields:
  code, section, text, type, options, required, safety, help, show_if, unit, min, max,
  exclusive (option value that excludes others in a multi), history_code (safety only).
Types: tri (نعم/لا) | choice | multi | text | longtext | date | number | scale010
Every question also supports the statuses UNKNOWN ("غير معروف") and NOT_ASKED ("لم يُسأل");
NOT_APPLICABLE ("لا ينطبق") only where `allow_na` is set.

show_if DSL: {"q": CODE, "eq": v} | {"q": CODE, "in": [..]} | {"q": CODE, "includes": v}
           | {"q": CODE, "includes_any": [..]} | {"q": CODE, "not_in": [..]} | {"q": CODE, "answered": true}
           | {"all": [...]} | {"any": [...]} | {"sex": "F"}
A question hidden by show_if is not required.
"""

YES_NO = None  # tri questions use fixed YES/NO values


def o(*pairs):
    return [{"v": v, "label": l} for v, l in pairs]


# ───────────────────────── Medical history (patient-level) ─────────────────────────
HISTORY_SECTIONS = [
    ("H2", "سبب الزيارة والمشكلة الحالية"),
    ("H3", "الأعراض الحالية"),
    ("H4", "أسئلة السلامة (إجابة المريض المسبقة)"),
    ("H5", "التاريخ الطبي"),
    ("H6", "العمليات الجراحية والإصابات السابقة"),
    ("H7", "الأدوية والحساسية"),
    ("H8", "الأجهزة المزروعة والمعادن داخل الجسم"),
    ("H9", "الفحوص والصور الطبية"),
    ("H10", "القدرة الحركية والوظيفية"),
    ("H11", "النشاط ونمط الحياة"),
    ("H12", "صحة المرأة"),
    ("H13", "أهداف المريض من برنامج التأهيل"),
    ("H14", "معلومات إضافية"),
    ("H15", "إقرار المريض (ورقي)"),
    ("H16", "قسم خاص بالفريق الطبي"),
]

CONDITIONS = [
    ("BLOOD", "اضطرابات دموية"), ("OSTEOPOROSIS", "هشاشة العظام"), ("HYPERTENSION", "ارتفاع ضغط الدم"),
    ("CIRCULATION", "ضعف/مشاكل بالدورة الدموية"), ("RHEUMATIC", "التهاب مفاصل روماتيزمي/مرض مناعي"),
    ("HEART", "أمراض القلب"), ("VTE", "جلطة وريدية أو صمة رئوية سابقة"), ("EPILEPSY", "صرع/نوبات اختلاج"),
    ("ARRHYTHMIA", "اضطراب نظم القلب"), ("CANCER", "سرطان حالي أو سابق"), ("PARKINSON", "باركنسون"),
    ("MI", "جلطة قلبية سابقة"), ("INFECTIOUS", "مرض معدٍ مهم"), ("MS", "التصلب المتعدد"),
    ("STROKE", "جلطة دماغية/نوبة نقص تروية"), ("PSYCH", "حالة نفسية/معرفية تؤثر على العلاج أو الحركة"),
    ("BRAIN_INJURY", "إصابة دماغية/عصبية سابقة"), ("DIABETES", "السكري"), ("KIDNEY", "أمراض الكلى"),
    ("THYROID", "أمراض الغدة الدرقية"), ("LIVER", "أمراض الكبد"), ("RESPIRATORY", "أمراض تنفسية/ربو"),
]

HISTORY_QUESTIONS = [
    # H2
    dict(code="HX_MAIN_PROBLEM", section="H2", type="longtext", text="ما المشكلة الأساسية التي يرغب المريض بعلاجها؟"),
    dict(code="HX_ONSET_DATE", section="H2", type="date", text="تاريخ بداية المشكلة"),
    dict(code="HX_AREA", section="H2", type="text", text="الجهة/المنطقة المصابة"),
    dict(code="HX_ONSET_MODE", section="H2", type="multi", text="كيف بدأت المشكلة؟", options=o(
        ("SUDDEN", "فجأة"), ("GRADUAL", "تدريجياً"), ("AFTER_INJURY", "بعد إصابة"), ("AFTER_SURGERY", "بعد عملية"),
        ("AFTER_ACCIDENT", "بعد حادث"), ("AFTER_NEURO", "بعد مرض/حالة عصبية"), ("NO_CAUSE", "دون سبب واضح"))),
    dict(code="HX_PREVIOUS_EPISODE", section="H2", type="tri", text="هل سبق أن عانى من المشكلة نفسها؟"),
    dict(code="HX_PREVIOUS_EPISODE_DETAILS", section="H2", type="longtext", text="متى وكيف عولجت؟",
         show_if={"q": "HX_PREVIOUS_EPISODE", "eq": "YES"}),
    # H3
    dict(code="HX_SYMPTOMS", section="H3", type="multi", text="الأعراض الحالية", options=o(
        ("PAIN", "ألم"), ("SWELLING", "تورم"), ("HAND_USE", "ضعف استخدام اليد/الطرف العلوي"), ("FATIGUE", "تعب سريع"),
        ("ROM_LOSS", "نقص مدى الحركة"), ("STIFFNESS", "تيبس"), ("WALKING", "صعوبة بالمشي"), ("WEAKNESS", "ضعف عضلي"),
        ("BALANCE", "اضطراب توازن"), ("NUMBNESS", "خدر/تنميل"), ("SPASM", "تشنجات عضلية"), ("BURNING", "حرقة"),
        ("OTHER", "أعراض أخرى"))),
    dict(code="HX_SYMPTOMS_OTHER", section="H3", type="text", text="أعراض أخرى (حدّد)",
         show_if={"q": "HX_SYMPTOMS", "includes": "OTHER"}),
    dict(code="HX_PAIN_NOW", section="H3", type="scale010", text="شدة الألم الآن (0–10)"),
    dict(code="HX_PAIN_MAX", section="H3", type="scale010", text="أشد ألم خلال أسبوع (0–10)"),
    dict(code="HX_PAIN_MIN", section="H3", type="scale010", text="أخف ألم خلال أسبوع (0–10)"),
    dict(code="HX_PATTERN", section="H3", type="choice", text="نمط الأعراض", options=o(("CONSTANT", "ثابتة/مستمرة"), ("INTERMITTENT", "متقطعة"))),
    dict(code="HX_TREND", section="H3", type="choice", text="اتجاه الأعراض حالياً", options=o(("IMPROVING", "تتحسن"), ("WORSENING", "تزداد"), ("SAME", "دون تغير"))),
    dict(code="HX_AGGRAVATING", section="H3", type="longtext", text="ما الذي يزيد الأعراض؟"),
    dict(code="HX_EASING", section="H3", type="longtext", text="ما الذي يخففها؟"),
    dict(code="HX_SLEEP", section="H3", type="choice", text="هل تؤثر الأعراض على النوم؟", options=o(("NO", "لا"), ("SOMETIMES", "أحياناً"), ("WAKES", "توقظه من النوم"))),
]

# H4: patient-reported safety answers (the clinician re-confirms them per episode; see SAFETY_QUESTIONS)
SAFETY_ITEMS = [
    # code suffix, text, tier
    ("CHEST_PAIN", "ألم أو ضغط غير معتاد في الصدر"),
    ("DYSPNEA", "ضيق نفس غير معتاد"),
    ("NIGHT_PAIN", "ألم شديد مستمر وغير معتاد ليلاً"),
    ("SADDLE_NUMBNESS", "خدر حديث حول المنطقة بين الفخذين/الأعضاء التناسلية (منطقة السرج)"),
    ("BLADDER_BOWEL_CONTROL", "فقدان أو تغيّر حديث في السيطرة على البول أو البراز"),
    ("PROGRESSIVE_WEAKNESS", "ضعف جديد أو سريع التفاقم في طرف"),
    ("SUDDEN_BALANCE_LOSS", "فقدان مفاجئ للتوازن أو القدرة على الحركة"),
    ("SIGNIFICANT_TRAUMA", "سقوط أو إصابة حديثة مهمة"),
    ("SYNCOPE", "إغماء أو دوار شديد حديث"),
    ("UNILATERAL_LEG_SWELLING", "تورم/ألم حديث وغير معتاد في ساق واحدة"),
    ("FEVER", "حمى/ارتفاع حرارة غير مفسَّر"),
    ("WEIGHT_LOSS", "نقص وزن غير مقصود"),
]
for suffix, text in SAFETY_ITEMS:
    HISTORY_QUESTIONS.append(dict(code="HX_SF_" + suffix, section="H4", type="tri", text=text))

for c, label in CONDITIONS:
    HISTORY_QUESTIONS.append(dict(code="HX_COND_" + c, section="H5", type="tri", text=label))

HISTORY_QUESTIONS += [
    dict(code="HX_COND_OTHER", section="H5", type="text", text="حالة أخرى"),
    dict(code="HX_COND_DETAILS", section="H5", type="longtext", text="تفاصيل مهمة، سنة التشخيص، أو حالة غير مذكورة"),
    # H6
    dict(code="HX_SURGERY_ANY", section="H6", type="tri", text="هل أجريت عمليات جراحية سابقاً؟",
         help="تفاصيل العمليات (العملية/المنطقة، السنة، ملاحظات) تُضاف في جدول العمليات أدناه."),
    dict(code="HX_INJURIES", section="H6", type="multi", text="هل سبق أن تعرض لأي مما يلي؟", options=o(
        ("FALL_INJURY", "سقوط أدى إلى إصابة"), ("SPINE", "إصابة أو عملية بالعمود الفقري"), ("JOINT_REPLACEMENT", "استبدال مفصل"),
        ("FRACTURE", "كسر"), ("DISLOCATION", "خلع"), ("LIGAMENT", "إصابة أربطة/أوتار"), ("SPORTS", "إصابة رياضية مهمة"),
        ("OTHER", "إصابة أخرى"), ("NONE", "لا شيء مما سبق")), exclusive="NONE"),
    dict(code="HX_INJURIES_DETAILS", section="H6", type="longtext", text="تفاصيل الإصابات",
         show_if={"q": "HX_INJURIES", "answered": True}),
    # H7
    dict(code="HX_MEDS_ANY", section="H7", type="tri", text="هل يتناول أدوية بشكل منتظم؟",
         help="اسم الدواء والجرعة والسبب تُضاف في جدول الأدوية أدناه."),
    dict(code="HX_MED_CLASSES", section="H7", type="multi", text="هل يستخدم أو استخدم مؤخراً أياً من التالي؟", options=o(
        ("STRONG_ANALGESICS", "مسكنات قوية"), ("ANTICOAGULANTS", "مميعات الدم"), ("CARDIAC", "أدوية القلب/الضغط"),
        ("STEROIDS", "كورتيزون (ستيرويدات)"), ("DIABETES", "أدوية السكري/الإنسولين"), ("ANTIEPILEPTIC", "أدوية الصرع"),
        ("OTHER", "أدوية أخرى مهمة"), ("NONE", "لا شيء مما سبق")), exclusive="NONE"),
    dict(code="HX_MED_OTHER", section="H7", type="text", text="أدوية أخرى مهمة (حدّد)",
         show_if={"q": "HX_MED_CLASSES", "includes": "OTHER"}),
    dict(code="HX_ALLERGY_ANY", section="H7", type="tri", text="هل لديه حساسية معروفة؟"),
    dict(code="HX_ALLERGIES", section="H7", type="multi", text="نوع الحساسية", options=o(
        ("ADHESIVES", "مواد لاصقة/ضمادات"), ("LATEX", "لاتكس"), ("DRUGS", "أدوية"), ("OTHER", "أخرى")),
         show_if={"q": "HX_ALLERGY_ANY", "eq": "YES"}),
    dict(code="HX_ALLERGY_DETAILS", section="H7", type="text", text="تفاصيل الحساسية",
         show_if={"q": "HX_ALLERGY_ANY", "eq": "YES"}),
    # H8
    dict(code="HX_IMPLANTS", section="H8", type="multi", text="الأجهزة المزروعة والمعادن داخل الجسم", options=o(
        ("PACEMAKER", "منظم ضربات القلب"), ("ICD", "مزيل رجفان مزروع"), ("NEUROSTIMULATOR", "محفز عصبي مزروع"),
        ("PUMP", "مضخة دوائية/إنسولين مزروعة"), ("COCHLEAR", "قوقعة مزروعة"), ("JOINT", "مفصل صناعي"),
        ("PLATES", "صفائح/براغي معدنية"), ("SPINE_IMPLANT", "زرعات في العمود الفقري"), ("OTHER", "زرعة/جهاز آخر"),
        ("NONE", "لا يوجد")), exclusive="NONE"),
    dict(code="HX_IMPLANT_DETAILS", section="H8", type="longtext", text="النوع، المكان، وتاريخ الزرع إن وجد",
         show_if={"q": "HX_IMPLANTS", "not_in": ["NONE"]}),
    # H9
    dict(code="HX_INVESTIGATIONS", section="H9", type="multi", text="الفحوص والصور الطبية", options=o(
        ("XRAY", "صورة شعاعية"), ("MRI", "رنين مغناطيسي"), ("CT", "طبقي محوري"), ("US", "تصوير بالأمواج فوق الصوتية"),
        ("EMG", "تخطيط أعصاب/عضلات"), ("LABS", "تحاليل مخبرية"), ("OTHER", "فحص آخر"), ("NONE", "لم يجرِ فحوصاً")),
         exclusive="NONE"),
    dict(code="HX_INVEST_DATE", section="H9", type="date", text="تاريخ آخر فحص",
         show_if={"q": "HX_INVESTIGATIONS", "not_in": ["NONE"]}),
    dict(code="HX_INVEST_AVAILABLE", section="H9", type="choice", text="التقارير/الصور", options=o(
        ("BROUGHT", "أحضرها معه"), ("UNAVAILABLE", "غير متوفرة")), show_if={"q": "HX_INVESTIGATIONS", "not_in": ["NONE"]}),
    dict(code="HX_INVEST_FINDING", section="H9", type="longtext", text="أهم نتيجة أو تشخيص معروف (كما ورد في التقرير)",
         show_if={"q": "HX_INVESTIGATIONS", "not_in": ["NONE"]}),
    # H10
    dict(code="HX_FUNC_PRIOR", section="H10", type="choice", text="قبل المشكلة الحالية كان", options=o(
        ("INDEPENDENT", "مستقلاً بالكامل"), ("MINOR_HELP", "يحتاج مساعدة بسيطة"), ("FREQUENT_HELP", "يحتاج مساعدة متكررة"),
        ("AID", "يستخدم وسيلة مساعدة"))),
    dict(code="HX_WALK_NOW", section="H10", type="choice", text="حالياً يستطيع المشي", options=o(
        ("UNAIDED", "دون مساعدة"), ("CANE", "بعصا"), ("CRUTCHES", "بعكازات"), ("WALKER", "بمشاية"), ("PERSON", "بمساعدة شخص"),
        ("WHEELCHAIR", "يستخدم كرسياً متحركاً"), ("UNABLE", "غير قادر على المشي حالياً"))),
    dict(code="HX_FALLS_12M", section="H10", type="choice", text="السقوط خلال آخر 12 شهراً", options=o(
        ("NONE", "لا"), ("ONCE", "مرة واحدة"), ("MULTIPLE", "أكثر من مرة"))),
    dict(code="HX_FEAR_FALLING", section="H10", type="tri", text="هل لديه خوف من السقوط؟"),
    dict(code="HX_ADL_HELP", section="H10", type="choice", text="هل يحتاج مساعدة في النشاطات اليومية؟", options=o(
        ("NO", "لا"), ("PARTIAL", "نعم جزئياً"), ("CLEAR", "نعم بشكل واضح"))),
    dict(code="HX_ADL_ITEMS", section="H10", type="multi", text="النشاطات التي يحتاج فيها مساعدة", options=o(
        ("TRANSFER", "الانتقال من السرير/الكرسي"), ("DRESSING", "اللباس"), ("STAIRS", "صعود الدرج"), ("BATHING", "الاستحمام"),
        ("OUTDOOR", "المشي خارج المنزل"), ("TOILET", "استخدام الحمام"), ("HAND_USE", "استخدام اليد في النشاطات اليومية"),
        ("OTHER", "أخرى")), show_if={"q": "HX_ADL_HELP", "in": ["PARTIAL", "CLEAR"]}),
    dict(code="HX_HARDEST_ACTIVITY", section="H10", type="longtext", text="ما أكثر نشاط أو حركة أصبحت صعبة بسبب المشكلة؟"),
    # H11
    dict(code="HX_ACTIVITY_LEVEL", section="H11", type="choice", text="مستوى النشاط قبل المشكلة", options=o(
        ("SEDENTARY", "قليل الحركة"), ("LIGHT", "نشاط خفيف"), ("MODERATE", "نشاط متوسط"), ("REGULAR_SPORT", "رياضة منتظمة"),
        ("HIGH", "رياضي/تدريب عالٍ"))),
    dict(code="HX_WORK_TYPE", section="H11", type="multi", text="طبيعة العمل", options=o(
        ("OFFICE", "مكتبي"), ("STANDING", "وقوف طويل"), ("PHYSICAL", "عمل بدني"), ("DRIVING", "قيادة طويلة"),
        ("RETIRED", "متقاعد"), ("OTHER", "أخرى"))),
    dict(code="HX_SMOKING", section="H11", type="choice", text="التدخين", options=o(("NO", "لا"), ("YES", "نعم"), ("FORMER", "كان يدخن وتوقف"))),
    dict(code="HX_HOME_AIDS", section="H11", type="multi", text="وسيلة مساعدة أو جهاز في المنزل", options=o(
        ("NONE", "لا"), ("CANE", "عصا"), ("WALKER", "مشاية"), ("WHEELCHAIR", "كرسي متحرك"), ("BRACE", "دعامة"), ("OTHER", "أخرى")),
         exclusive="NONE"),
    # H12
    dict(code="HX_PREGNANCY", section="H12", type="choice", text="هل يوجد حمل حالياً أو احتمال وجود حمل؟", options=o(
        ("NO", "لا"), ("YES", "نعم"), ("UNSURE", "غير متأكدة")), show_if={"sex": "F"}, allow_na=True),
    # H13
    dict(code="HX_GOALS", section="H13", type="multi", text="هدف المريض من برنامج التأهيل", options=o(
        ("PAIN", "تخفيف الألم"), ("STRENGTH", "زيادة القوة"), ("ROM", "زيادة مدى الحركة"), ("WALKING", "المشي بشكل أفضل"),
        ("BALANCE", "تحسين التوازن"), ("HAND", "تحسين استخدام اليد/الطرف العلوي"), ("WORK", "العودة للعمل"),
        ("SPORT", "العودة للرياضة"), ("POST_SURGERY", "التعافي بعد عملية"), ("PREVENTION", "الوقاية من تكرار الإصابة"),
        ("INDEPENDENCE", "استعادة الاستقلال بالنشاطات اليومية"), ("OTHER", "هدف آخر"))),
    dict(code="HX_MAIN_GOAL", section="H13", type="longtext", text="«بنهاية البرنامج أتمنى أن أستطيع…» (أهم هدف بالنسبة للمريض)"),
    # H14
    dict(code="HX_ADDITIONAL", section="H14", type="longtext", text="أي شيء متعلق بالصحة أو العلاج مهم أن يعرفه الفريق؟"),
    # H15
    dict(code="HX_DECLARATION_PAPER", section="H15", type="tri",
         text="هل وقّع المريض/الوصي إقرار المعلومات الورقي؟",
         help="النظام لا يسجّل إقراراً أو توقيعاً نيابة عن المريض. هذا الحقل تصريح من الموظف بوجود إقرار ورقي موقّع في الملف."),
    dict(code="HX_DECLARATION_SIGNER", section="H15", type="text", text="اسم الموقّع وصلته بالمريض (إن كان وصياً)",
         show_if={"q": "HX_DECLARATION_PAPER", "eq": "YES"}),
    # H16 clinical use
    dict(code="CLIN_REVIEWED_WITH_PATIENT", section="H16", type="tri", text="تمت مراجعة الاستبيان مع المريض"),
    dict(code="CLIN_FURTHER_INVESTIGATION", section="H16", type="longtext",
         text="عوامل تستدعي استكمال الاستقصاء قبل العلاج (تفاصيل)"),
    dict(code="CLIN_RISK_CLASS", section="H16", type="choice", text="تصنيف الخطورة الأولي (يحدده المراجع)", options=o(
        ("LOW", "منخفض"), ("MEDIUM", "متوسط - يحتاج احتياطات/تعديل"), ("HIGH", "مرتفع - يؤجل العلاج لحين التقييم الطبي")),
         help="لا يحسبه النظام آلياً. يُعرض بجانبه ناتج فرز السلامة للحلقة."),
    dict(code="CLIN_NOTES", section="H16", type="longtext", text="ملاحظات سريرية مهمة من التاريخ المرضي"),
]

# ───────────────────────── Lumbar assessment (episode-level) ─────────────────────────
LUMBAR_SECTIONS = [
    ("INFO", "معلومات الحالة"),
    ("SAFETY", "فرز السلامة"),
    ("SYMPTOMS", "الشكوى والأعراض"),
    ("BRANCH_NEURO", "الأعراض العصبية والامتداد للطرف"),
    ("BRANCH_STANDING", "نمط يزداد بالوقوف/المشي"),
    ("BRANCH_SURGERY", "جراحة سابقة أو حديثة"),
    ("BRANCH_TRAUMA", "إصابة/رضّ"),
    ("IMAGING", "الصور الطبية"),
    ("FUNCTION", "الوظيفة والعوامل النفسية الاجتماعية"),
    ("SUMMARY", "الملخص والانطباع السريري"),
]

# Safety questions: tier = EMERGENCY | URGENT | REVIEW. All are mandatory.
SAFETY_QUESTIONS = [
    dict(code="SF_URINARY_RETENTION", text="احتباس بول حديث أو صعوبة جديدة في بدء التبول", tier="EMERGENCY", group="CES"),
    dict(code="SF_BLADDER_BOWEL_CONTROL", text="فقدان أو تغيّر حديث في السيطرة على البول أو البراز", tier="EMERGENCY", group="CES",
         history_code="HX_SF_BLADDER_BOWEL_CONTROL"),
    dict(code="SF_SADDLE_NUMBNESS", text="خدر أو تغيّر إحساس حديث في منطقة السرج (بين الفخذين/حول الشرج والأعضاء التناسلية)",
         tier="EMERGENCY", group="CES", history_code="HX_SF_SADDLE_NUMBNESS"),
    dict(code="SF_BILATERAL_LEG_SYMPTOMS", text="أعراض عصبية حديثة في الساقين معاً (ألم/خدر/ضعف)", tier="REVIEW", group="CES"),
    dict(code="SF_SEXUAL_DYSFUNCTION_NEW", text="تغيّر حديث في الوظيفة الجنسية مرتبط بأعراض الظهر (يُسأل بشكل مهني مناسب)",
         tier="REVIEW", group="CES", allow_na=True),
    dict(code="SF_PROGRESSIVE_WEAKNESS", text="ضعف جديد أو سريع التفاقم في طرف", tier="EMERGENCY", group="NEURO",
         history_code="HX_SF_PROGRESSIVE_WEAKNESS"),
    dict(code="SF_SUDDEN_BALANCE_LOSS", text="فقدان مفاجئ للتوازن أو القدرة على الحركة، أو اضطراب عصبي شديد مفاجئ",
         tier="EMERGENCY", group="NEURO", history_code="HX_SF_SUDDEN_BALANCE_LOSS"),
    dict(code="SF_CHEST_PAIN", text="ألم أو ضغط غير معتاد في الصدر", tier="EMERGENCY", group="CARDIO",
         history_code="HX_SF_CHEST_PAIN"),
    dict(code="SF_DYSPNEA", text="ضيق نفس غير معتاد أو حديث", tier="EMERGENCY", group="CARDIO", history_code="HX_SF_DYSPNEA"),
    dict(code="SF_ACUTE_VASCULAR", text="ألم بطني أو ظهري شديد مفاجئ مختلف عن المعتاد (قد يكون نابضاً)", tier="EMERGENCY",
         group="CARDIO"),
    dict(code="SF_UNILATERAL_LEG_SWELLING", text="تورم/ألم حديث وغير معتاد في ساق واحدة", tier="URGENT", group="CARDIO",
         history_code="HX_SF_UNILATERAL_LEG_SWELLING"),
    dict(code="SF_SYNCOPE", text="إغماء أو دوار شديد حديث", tier="URGENT", group="CARDIO", history_code="HX_SF_SYNCOPE"),
    dict(code="SF_SIGNIFICANT_TRAUMA", text="سقوط أو إصابة حديثة مهمة قبل بدء الألم أو تفاقمه", tier="REVIEW", group="FRACTURE",
         history_code="HX_SF_SIGNIFICANT_TRAUMA"),
    dict(code="SF_FEVER", text="حمى/ارتفاع حرارة غير مفسَّر", tier="URGENT", group="INFECTION", history_code="HX_SF_FEVER"),
    dict(code="SF_INFECTION_RISK", text="عوامل خطر عدوى: كبت مناعة، إجراء جراحي/حقن في الظهر حديثاً، عدوى حديثة، تعاطي حقن وريدية",
         tier="REVIEW", group="INFECTION"),
    dict(code="SF_CANCER_HISTORY", text="سرطان حالي أو سابق", tier="REVIEW", group="MALIGNANCY",
         history_code="HX_COND_CANCER"),
    dict(code="SF_WEIGHT_LOSS", text="نقص وزن غير مقصود", tier="REVIEW", group="MALIGNANCY", history_code="HX_SF_WEIGHT_LOSS"),
    dict(code="SF_NIGHT_PAIN", text="ألم ليلي شديد مستمر غير مرتبط بالوضعية وغير معتاد", tier="REVIEW", group="MALIGNANCY",
         history_code="HX_SF_NIGHT_PAIN"),
    dict(code="SF_SYSTEMIC_UNWELL", text="شعور عام بالمرض/تعب شديد غير مفسر حديثاً", tier="REVIEW", group="MALIGNANCY"),
]

LUMBAR_QUESTIONS = [
    # INFO
    dict(code="LB_PRESENTING_PROBLEM", section="INFO", type="longtext", text="المشكلة الحالية بكلمات المريض", required=True),
    dict(code="LB_ONSET_DATE", section="INFO", type="date", text="تاريخ بداية النوبة الحالية"),
    dict(code="LB_ONSET_MODE", section="INFO", type="choice", text="طريقة البداية", required=True, options=o(
        ("GRADUAL", "تدريجية"), ("SUDDEN", "مفاجئة دون رضّ"), ("AFTER_TRAUMA", "بعد رضّ/سقوط/حادث"),
        ("AFTER_SURGERY", "بعد عملية"), ("NO_CLEAR_CAUSE", "دون سبب واضح"))),
    dict(code="LB_DURATION_CATEGORY", section="INFO", type="choice", text="مدة النوبة الحالية", required=True, options=o(
        ("ACUTE", "أقل من 6 أسابيع"), ("SUBACUTE", "6–12 أسبوعاً"), ("CHRONIC", "أكثر من 12 أسبوعاً"))),
    dict(code="LB_PREVIOUS_EPISODES", section="INFO", type="tri", text="نوبات سابقة مشابهة؟"),
    dict(code="LB_PREVIOUS_EPISODES_DETAILS", section="INFO", type="longtext", text="عدد النوبات والعلاج السابق ونتيجته",
         show_if={"q": "LB_PREVIOUS_EPISODES", "eq": "YES"}),
    dict(code="LB_TREND", section="INFO", type="choice", text="تطور الحالة", options=o(
        ("IMPROVING", "تتحسن"), ("WORSENING", "تسوء"), ("SAME", "ثابتة"), ("FLUCTUATING", "متذبذبة"))),
    # SYMPTOMS
    dict(code="LB_PAIN_LOCATION", section="SYMPTOMS", type="multi", text="موضع الألم في الظهر", required=True, options=o(
        ("CENTRAL", "منتصف"), ("RIGHT", "يمين"), ("LEFT", "يسار"))),
    dict(code="LB_DISTRIBUTION", section="SYMPTOMS", type="choice", required=True,
         text="أبعد امتداد للأعراض", help="القيمة الافتراضية «لم يُسأل». لا تفترض أن الألم محصور بالظهر قبل السؤال.",
         options=o(("BACK_ONLY", "محصور في الظهر"), ("BUTTOCK", "حتى الألية"), ("THIGH", "حتى الفخذ"),
                   ("BELOW_KNEE", "أسفل الركبة/الساق"), ("FOOT", "حتى القدم"))),
    dict(code="LB_DISTRIBUTION_SIDE", section="SYMPTOMS", type="choice", text="جهة الامتداد", required=True, options=o(
        ("RIGHT", "يمين"), ("LEFT", "يسار"), ("BOTH", "الجهتان"), ("ALTERNATING", "متناوب")),
         show_if={"q": "LB_DISTRIBUTION", "in": ["BUTTOCK", "THIGH", "BELOW_KNEE", "FOOT"]}),
    dict(code="LB_BODY_MAP_NOTE", section="SYMPTOMS", type="text", text="ملاحظة على خريطة الأعراض (اختياري)"),
    dict(code="LB_PAIN_NOW", section="SYMPTOMS", type="scale010", text="شدة الألم الآن (0–10)", required=True),
    dict(code="LB_PAIN_MIN_WEEK", section="SYMPTOMS", type="scale010", text="أخف ألم خلال الأسبوع (0–10)"),
    dict(code="LB_PAIN_MAX_WEEK", section="SYMPTOMS", type="scale010", text="أشد ألم خلال الأسبوع (0–10)"),
    dict(code="LB_PAIN_SOURCE", section="SYMPTOMS", type="choice", text="مصدر قياس الألم", options=o(
        ("PATIENT_NOW", "تقرير المريض أثناء التقييم"), ("PRE_FORM", "من الاستبيان المسبق"), ("PROXY", "من المرافق"))),
    dict(code="LB_PAIN_NATURE", section="SYMPTOMS", type="multi", text="طبيعة الألم", options=o(
        ("ACHING", "وجع/ثقل"), ("SHARP", "حاد/طاعن"), ("BURNING", "حارق"), ("SHOOTING", "صاعق/ممتد"),
        ("TIGHTNESS", "شد/تيبس"), ("OTHER", "أخرى"))),
    dict(code="LB_PATTERN", section="SYMPTOMS", type="choice", text="مستمر أم متقطع", options=o(
        ("CONSTANT", "مستمر"), ("INTERMITTENT", "متقطع"))),
    dict(code="LB_PAIN_CONTEXT", section="SYMPTOMS", type="multi", text="يظهر الألم مع", options=o(
        ("REST", "الراحة"), ("MOVEMENT", "الحركة"), ("NIGHT", "الليل"))),
    dict(code="LB_SLEEP", section="SYMPTOMS", type="choice", text="الليل والنوم", options=o(
        ("NO_EFFECT", "لا يؤثر"), ("POSITION", "يوقظه عند تغيير الوضعية"), ("WAKES_OFTEN", "يوقظه كثيراً بغض النظر عن الوضعية"))),
    dict(code="LB_MORNING_STIFFNESS", section="SYMPTOMS", type="choice", text="تيبس صباحي", options=o(
        ("NONE", "لا يوجد"), ("LT30", "أقل من 30 دقيقة"), ("GT30", "أكثر من 30 دقيقة"))),
    dict(code="LB_AGG", section="SYMPTOMS", type="multi", text="المحرّضات (ما يزيد الأعراض)", required=True, options=o(
        ("SITTING", "الجلوس"), ("STANDING", "الوقوف"), ("WALKING", "المشي"), ("BENDING_FWD", "الانحناء للأمام"),
        ("EXTENSION", "التمدد للخلف"), ("LIFTING", "الرفع"), ("COUGH_SNEEZE", "السعال/العطاس"),
        ("TRANSITIONS", "تغيير الوضعية/النهوض"), ("LYING", "الاستلقاء"))),
    dict(code="LB_EASE", section="SYMPTOMS", type="multi", text="المخففات", options=o(
        ("SITTING", "الجلوس"), ("FLEXION", "الانحناء للأمام/الثني"), ("LYING", "الاستلقاء"), ("WALKING", "المشي"),
        ("EXTENSION", "التمدد للخلف"), ("MOVEMENT", "الحركة عموماً"), ("REST", "الراحة"), ("HEAT", "الحرارة"),
        ("MEDICATION", "الدواء"))),
    dict(code="LB_SIT_TOLERANCE_MIN", section="SYMPTOMS", type="number", unit="دقيقة", min=0, max=600,
         text="أقصى زمن جلوس قبل زيادة الأعراض", show_if={"q": "LB_AGG", "includes": "SITTING"}),
    dict(code="LB_STAND_TOLERANCE_MIN", section="SYMPTOMS", type="number", unit="دقيقة", min=0, max=600,
         text="أقصى زمن وقوف قبل زيادة الأعراض", show_if={"q": "LB_AGG", "includes": "STANDING"}),
    dict(code="LB_WALK_TOLERANCE_MIN", section="SYMPTOMS", type="number", unit="دقيقة", min=0, max=600,
         text="أقصى زمن مشي قبل التوقف بسبب الأعراض", show_if={"q": "LB_AGG", "includes": "WALKING"}),
    dict(code="LB_NEURO_SYMPTOMS", section="SYMPTOMS", type="multi", text="أعراض عصبية", required=True, options=o(
        ("NUMBNESS", "تنميل/خدر"), ("TINGLING", "وخز"), ("WEAKNESS", "ضعف"), ("GAIT", "اختلال بالمشي"),
        ("BALANCE", "اختلال بالتوازن"), ("NONE", "لا يوجد")), exclusive="NONE"),
    dict(code="LB_HISTORY_NARRATIVE", section="SYMPTOMS", type="longtext", text="القصة المرضية (سرد مختصر)"),
    # BRANCH_NEURO (leg / neuro)
    dict(code="LB_NEURO_DISTRIBUTION", section="BRANCH_NEURO", type="longtext", required=True,
         text="توزع الألم/التنميل في الطرف (وصف دقيق للمنطقة)",
         show_if={"any": [{"q": "LB_DISTRIBUTION", "in": ["THIGH", "BELOW_KNEE", "FOOT", "BUTTOCK"]},
                          {"q": "LB_NEURO_SYMPTOMS", "includes_any": ["NUMBNESS", "TINGLING", "WEAKNESS"]}]}),
    dict(code="LB_LEG_VS_BACK", section="BRANCH_NEURO", type="choice", text="أيهما أشد", options=o(
        ("LEG", "الساق أشد من الظهر"), ("BACK", "الظهر أشد"), ("EQUAL", "متساويان")),
         show_if={"q": "LB_DISTRIBUTION", "in": ["THIGH", "BELOW_KNEE", "FOOT"]}),
    dict(code="LB_NEURO_CHANGE", section="BRANCH_NEURO", type="choice", required=True, text="تغيّر الأعراض العصبية منذ البداية",
         options=o(("BETTER", "تتحسن"), ("STABLE", "ثابتة"), ("WORSE_SLOW", "تسوء ببطء"), ("WORSE_FAST", "تسوء بسرعة")),
         show_if={"q": "LB_NEURO_SYMPTOMS", "includes_any": ["NUMBNESS", "TINGLING", "WEAKNESS", "GAIT", "BALANCE"]}),
    # BRANCH_STANDING (neurogenic vs vascular differentiation)
    dict(code="LB_NC_RELIEF_POSITION", section="BRANCH_STANDING", type="choice", required=True,
         text="عند ظهور الأعراض أثناء المشي، ما الذي يخففها؟", options=o(
             ("SIT_OR_FLEX", "الجلوس أو الانحناء للأمام"), ("STOP_STANDING", "التوقف واقفاً يكفي"),
             ("EITHER", "كلاهما"), ("NONE", "لا شيء يخففها بسرعة")),
         show_if={"all": [{"q": "LB_AGG", "includes_any": ["STANDING", "WALKING"]},
                          {"q": "LB_EASE", "includes_any": ["SITTING", "FLEXION"]}]}),
    dict(code="LB_NC_INCLINE", section="BRANCH_STANDING", type="choice", text="الأعراض أسوأ عند", options=o(
        ("DOWNHILL", "النزول/المشي منتصباً"), ("UPHILL", "الصعود"), ("NO_DIFF", "لا فرق")),
         show_if={"all": [{"q": "LB_AGG", "includes_any": ["STANDING", "WALKING"]},
                          {"q": "LB_EASE", "includes_any": ["SITTING", "FLEXION"]}]}),
    dict(code="LB_NC_BIKE", section="BRANCH_STANDING", type="tri", text="يتحمل الدراجة أو المشي منحنياً (عربة تسوق) أفضل من المشي المنتصب؟",
         show_if={"all": [{"q": "LB_AGG", "includes_any": ["STANDING", "WALKING"]},
                          {"q": "LB_EASE", "includes_any": ["SITTING", "FLEXION"]}]}),
    dict(code="LB_VASC_RISK", section="BRANCH_STANDING", type="multi", text="عوامل/علامات وعائية", required=True, options=o(
        ("SMOKING", "تدخين"), ("DIABETES", "سكري"), ("KNOWN_PAD", "مرض شرياني معروف"), ("COLD_PALE", "برودة/شحوب القدم"),
        ("NONE", "لا يوجد")), exclusive="NONE",
         show_if={"all": [{"q": "LB_AGG", "includes_any": ["STANDING", "WALKING"]},
                          {"q": "LB_EASE", "includes_any": ["SITTING", "FLEXION"]}]}),
    dict(code="LB_PULSES_NOTE", section="BRANCH_STANDING", type="text", text="نبض القدمين (إن فُحص) وأي ملاحظات وعائية",
         show_if={"all": [{"q": "LB_AGG", "includes_any": ["STANDING", "WALKING"]},
                          {"q": "LB_EASE", "includes_any": ["SITTING", "FLEXION"]}]}),
    # BRANCH_SURGERY
    dict(code="LB_SPINE_SURGERY", section="BRANCH_SURGERY", type="tri", text="عملية سابقة أو حديثة في العمود القطني؟", required=True),
    dict(code="LB_SURG_TYPE", section="BRANCH_SURGERY", type="text", text="نوع العملية والمستوى (كما في التقرير)", required=True,
         show_if={"any": [{"q": "LB_SPINE_SURGERY", "eq": "YES"}, {"q": "LB_ONSET_MODE", "eq": "AFTER_SURGERY"}]}),
    dict(code="LB_SURG_DATE", section="BRANCH_SURGERY", type="date", text="تاريخ العملية", required=True,
         show_if={"any": [{"q": "LB_SPINE_SURGERY", "eq": "YES"}, {"q": "LB_ONSET_MODE", "eq": "AFTER_SURGERY"}]}),
    dict(code="LB_SURG_INSTRUCTIONS", section="BRANCH_SURGERY", type="choice", text="تعليمات الجراح وقيود الحركة/التحميل",
         required=True, options=o(("DOCUMENTED", "موجودة وموثقة أدناه"), ("NONE_GIVEN", "أكد الجراح عدم وجود قيود"),
                                  ("NOT_AVAILABLE", "غير متوفرة بعد")),
         help="إذا كانت «غير متوفرة بعد» لا يمكن إرسال خطة للاعتماد حتى تتضح القيود.",
         show_if={"any": [{"q": "LB_SPINE_SURGERY", "eq": "YES"}, {"q": "LB_ONSET_MODE", "eq": "AFTER_SURGERY"}]}),
    dict(code="LB_SURG_RESTRICTIONS", section="BRANCH_SURGERY", type="longtext", text="القيود والتعليمات بالتفصيل", required=True,
         show_if={"q": "LB_SURG_INSTRUCTIONS", "eq": "DOCUMENTED"}),
    dict(code="LB_SURG_COMPLICATIONS", section="BRANCH_SURGERY", type="multi", text="علامات مضاعفات", required=True, options=o(
        ("WOUND", "احمرار/إفرازات بالجرح"), ("FEVER", "حرارة"), ("NEW_DEFICIT", "عجز عصبي جديد"),
        ("RISING_PAIN", "ألم متزايد غير متوقع"), ("NONE", "لا يوجد")), exclusive="NONE",
         show_if={"any": [{"q": "LB_SPINE_SURGERY", "eq": "YES"}, {"q": "LB_ONSET_MODE", "eq": "AFTER_SURGERY"}]}),
    dict(code="LB_SURG_REPORT_ATTACHED", section="BRANCH_SURGERY", type="tri", text="تقرير العملية مرفق بملف المريض؟",
         show_if={"any": [{"q": "LB_SPINE_SURGERY", "eq": "YES"}, {"q": "LB_ONSET_MODE", "eq": "AFTER_SURGERY"}]}),
    # BRANCH_TRAUMA
    dict(code="LB_TRAUMA_MECHANISM", section="BRANCH_TRAUMA", type="longtext", text="آلية الإصابة (ارتفاع السقوط، نوع الحادث…)",
         required=True, show_if={"any": [{"q": "LB_ONSET_MODE", "eq": "AFTER_TRAUMA"}, {"q": "SF_SIGNIFICANT_TRAUMA", "eq": "YES"}]}),
    dict(code="LB_TRAUMA_DATE", section="BRANCH_TRAUMA", type="date", text="تاريخ الإصابة",
         show_if={"any": [{"q": "LB_ONSET_MODE", "eq": "AFTER_TRAUMA"}, {"q": "SF_SIGNIFICANT_TRAUMA", "eq": "YES"}]}),
    dict(code="LB_FRACTURE_EXCLUDED", section="BRANCH_TRAUMA", type="choice", required=True,
         text="هل استُبعد الكسر طبياً؟", options=o(("YES_DOCUMENTED", "نعم، بتقرير/تقييم طبي موثّق"), ("NO", "لا")),
         help="إن لم يُستبعد، تُحجب الاختبارات التحميلية/الاستفزازية ويُطلب تقييم طبي.",
         show_if={"any": [{"q": "LB_ONSET_MODE", "eq": "AFTER_TRAUMA"}, {"q": "SF_SIGNIFICANT_TRAUMA", "eq": "YES"}]}),
    # IMAGING
    dict(code="LB_IMAGING_TYPE", section="IMAGING", type="multi", text="الصور الطبية المتوفرة", options=o(
        ("XRAY", "شعاعية"), ("MRI", "رنين"), ("CT", "طبقي محوري"), ("EMG", "تخطيط أعصاب"), ("NONE", "لا يوجد")), exclusive="NONE"),
    dict(code="LB_IMAGING_DATE", section="IMAGING", type="date", text="تاريخ آخر صورة",
         show_if={"q": "LB_IMAGING_TYPE", "not_in": ["NONE"]}),
    dict(code="LB_IMAGING_REPORT_TEXT", section="IMAGING", type="longtext", text="ما يقوله التقرير (انقل ملخص التقرير كما هو)",
         show_if={"q": "LB_IMAGING_TYPE", "not_in": ["NONE"]}),
    dict(code="LB_IMAGING_CLINICAL_RELEVANCE", section="IMAGING", type="longtext",
         text="الانطباع السريري: هل تتوافق موجودات التقرير مع الأعراض والفحص؟",
         help="موجودات الرنين شائعة لدى أشخاص بلا أعراض. لا يُحدَّد مستوى الجذر العصبي من تقرير الرنين وحده.",
         show_if={"q": "LB_IMAGING_TYPE", "not_in": ["NONE"]}),
    # FUNCTION
    dict(code="LB_WORK_IMPACT", section="FUNCTION", type="choice", text="التأثير على العمل", options=o(
        ("NONE", "لا تأثير"), ("MODIFIED", "يعمل بمهام معدلة"), ("OFF_WORK", "متوقف عن العمل"), ("NA", "لا يعمل حالياً لأسباب أخرى"))),
    dict(code="LB_ACTIVITY_LIMITS", section="FUNCTION", type="longtext", text="النشاطات المحدودة حالياً (منزل/عمل/رياضة)", required=True),
    dict(code="LB_CONCERN_MOVEMENT", section="FUNCTION", type="choice", text="قلق المريض من أن الحركة ستؤذي ظهره", options=o(
        ("NONE", "لا"), ("SOME", "قليل"), ("HIGH", "كبير"))),
    dict(code="LB_PATIENT_UNDERSTANDING", section="FUNCTION", type="longtext", text="فهم المريض لسبب الألم وتوقعاته من العلاج"),
    dict(code="LB_MOOD_IMPACT", section="FUNCTION", type="choice", text="تأثير الألم على المزاج/النوم/الحياة الاجتماعية (كما يصفه المريض)",
         options=o(("NONE", "لا يذكر تأثيراً"), ("SOME", "تأثير بسيط"), ("MARKED", "تأثير واضح"))),
    # SUMMARY
    dict(code="LB_PAIN_CLASSIFICATION", section="SUMMARY", type="choice", required=True,
         text="التصنيف السريري المبدئي (انطباع، ليس تشخيصاً نهائياً)", options=o(
             ("LOCAL", "ألم ظهر موضعي غالباً"), ("REFERRED", "ألم ظهر مع ألم منتشر للطرف دون علامات عصبية واضحة"),
             ("RADICULAR_SIGNS", "ألم ظهر مع علامات توحي باعتلال جذر عصبي (حسب الفحص)"),
             ("CLAUDICATION_PATTERN", "نمط يزداد بالوقوف/المشي ويخف بالجلوس، يحتاج تفريقاً عصبياً/وعائياً"),
             ("POST_SURGICAL", "ما بعد جراحة"), ("UNCERTAIN", "غير محسوم، يحتاج تقييماً إضافياً"))),
    dict(code="LB_CERTAINTY", section="SUMMARY", type="choice", text="درجة اليقين", required=True, options=o(
        ("LOW", "منخفضة"), ("MODERATE", "متوسطة"), ("HIGH", "مرتفعة"))),
    dict(code="LB_CLINICAL_IMPRESSION", section="SUMMARY", type="longtext", text="الانطباع السريري والمبررات", required=True),
    dict(code="LB_DIFFERENTIALS", section="SUMMARY", type="longtext", text="بدائل/احتمالات أخرى تحتاج متابعة"),
    dict(code="LB_GENERAL_NOTES", section="SUMMARY", type="longtext", text="ملاحظات عامة"),
]

for i, sq in enumerate(SAFETY_QUESTIONS):
    q = dict(code=sq["code"], section="SAFETY", type="tri", text=sq["text"], required=True, safety=True,
             tier=sq["tier"], group=sq["group"])
    if sq.get("history_code"):
        q["history_code"] = sq["history_code"]
    if sq.get("allow_na"):
        q["allow_na"] = True
    LUMBAR_QUESTIONS.insert(7 + i, q)  # after INFO questions, order is by section anyway


QUESTIONNAIRES = {
    "MEDICAL_HISTORY": {"name": "استبيان التاريخ الطبي والتقييم الأولي", "sections": HISTORY_SECTIONS,
                        "questions": HISTORY_QUESTIONS, "scope": "patient"},
    "LUMBAR_ASSESSMENT": {"name": "تقييم أسفل الظهر (العمود القطني)", "sections": LUMBAR_SECTIONS,
                          "questions": LUMBAR_QUESTIONS, "scope": "episode"},
}
