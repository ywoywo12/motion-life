"""Seed content for catalogs (tests, equipment, outcome measures).

CLINICAL CONTENT NOTICE: written conservatively by the developer from general physiotherapy
practice. It is published as version 1 so the pathway can be tried, but it MUST be reviewed
and re-published by an authorised clinician of the centre before real use (see README).
"""

REVIEW_NOTE = "محتوى أولي من المطوّر — يتطلب مراجعة واعتماداً سريرياً من المركز قبل الاستخدام الفعلي"

LEVELS_MYO = [("L2", "ثني الورك"), ("L3", "بسط الركبة"), ("L4", "رفع ظهر القدم (عطف ظهري للكاحل)"),
              ("L5", "بسط إبهام القدم"), ("S1", "عطف أخمصي للكاحل/الوقوف على المشطين")]
LEVELS_DERM = [("L2", "الفخذ الأمامي العلوي"), ("L3", "الفخذ الأمامي السفلي/الركبة"), ("L4", "الساق الإنسية/الكاحل الإنسي"),
               ("L5", "ظهر القدم/الإبهام"), ("S1", "الحافة الوحشية للقدم/الكعب")]
REFLEXES = [("PATELLAR", "منعكس الرضفة (L3–L4)"), ("ACHILLES", "منعكس وتر أخيل (S1)")]

TESTS = [
    dict(code="OBS_FUNCTION", name_ar="المراقبة الوظيفية والوضعية", name_en="Functional observation", category="observation",
         result_type="text", sides=False, provocative=False,
         indication="كل الحالات: الوضعية، طريقة الجلوس والنهوض، سلوك الألم.",
         safety="لا قيود خاصة.", position="جلوس ووقوف ومشي طبيعي",
         steps="راقب الوضعية والانتقالات (جلوس↔وقوف) وسلوك الحماية دون تعليق على «صدق» الألم.",
         positive="لا يوجد إيجابي/سلبي؛ توصيف.", limits="المراقبة لا تحدد مصدر الألم."),
    dict(code="MOVEMENT_PATTERN", name_ar="نمط الحركة", name_en="Movement pattern / quality", category="observation",
         result_type="text", sides=False, provocative=False,
         indication="كل الحالات.", safety="توقف عند زيادة واضحة للأعراض.", position="وقوف",
         steps="لاحظ جودة الحركة والتعويض أثناء الانثناء والبسط والميلان.",
         positive="توصيف.", limits="ضعف جودة الحركة لا يعني وجود إصابة بنيوية."),
    dict(code="ROM_FLEX", name_ar="مدى الانثناء القطني", name_en="Lumbar flexion ROM", category="rom", result_type="rom",
         sides=False, unit="سم (أصابع-أرض)", provocative=False,
         indication="كل الحالات غير المحجوبة.", safety="يُحجب عند احتمال كسر غير مستبعد.", position="وقوف",
         steps="انحناء للأمام بالركبتين مستقيمتين، قِس المسافة بين الأصابع والأرض وسجّل الأعراض المرافقة.",
         positive="قيمة كمية + الأعراض (لا ألم/ألم موضعي/ألم منتشر).", limits="يتأثر بمرونة الورك والخلفية.",
         blocked_by=["SUSPECTED_FRACTURE"]),
    dict(code="ROM_EXT", name_ar="مدى البسط القطني", name_en="Lumbar extension ROM", category="rom", result_type="rom",
         sides=False, unit="تقدير (طبيعي/محدود قليلاً/محدود كثيراً)", provocative=False,
         indication="كل الحالات غير المحجوبة.", safety="يُحجب عند احتمال كسر غير مستبعد.", position="وقوف",
         steps="تمدد للخلف مع تثبيت الحوض، سجّل المدى التقديري والأعراض.",
         positive="توصيف المدى والأعراض.", limits="التقدير البصري محدود الموثوقية.", blocked_by=["SUSPECTED_FRACTURE"]),
    dict(code="ROM_SIDEFLEX", name_ar="الميلان الجانبي", name_en="Lateral flexion", category="rom", result_type="rom",
         sides=True, unit="سم (الإصبع الأوسط على الفخذ)", provocative=False,
         indication="كل الحالات غير المحجوبة.", safety="يُحجب عند احتمال كسر غير مستبعد.", position="وقوف",
         steps="ميلان جانبي مع انزلاق اليد على الفخذ، قِس الفرق، لكل جهة.",
         positive="قيمة لكل جهة + الأعراض.", limits="—", blocked_by=["SUSPECTED_FRACTURE"]),
    dict(code="GAIT", name_ar="تقييم المشي", name_en="Gait observation", category="function", result_type="text",
         sides=False, provocative=False,
         indication="أعراض عصبية، اضطراب توازن، أو نمط يزداد بالمشي.", safety="وسيلة مساعدة ومرافقة عند خطر السقوط.",
         position="مشي على مسافة آمنة", steps="لاحظ النمط، سقوط القدم، العرج، الحاجة للتوقف.",
         positive="توصيف.", limits="—", recommend_if={"any": [
             {"q": "LB_NEURO_SYMPTOMS", "includes_any": ["GAIT", "BALANCE", "WEAKNESS"]},
             {"q": "LB_AGG", "includes_any": ["WALKING", "STANDING"]}]}),
    dict(code="WALK_TEST", name_ar="اختبار تحمّل المشي الموقوت", name_en="Timed walking tolerance", category="function",
         result_type="value", sides=False, unit="دقيقة", provocative=False,
         indication="أعراض تزداد بالوقوف/المشي.", safety="يُوقف عند أعراض صدرية/دوار أو ألم شديد؛ يُحجب مع علامات وعائية/قلبية حادة.",
         position="مشي بسرعة مريحة", steps="سجّل الزمن حتى بدء الأعراض والزمن حتى التوقف، والوضعية التي خففت الأعراض.",
         positive="قيمة كمية + ما خفف الأعراض (جلوس/انحناء مقابل الوقوف فقط).",
         limits="لا يميّز وحده بين الأسباب العصبية والوعائية؛ يُقرأ مع النبض والتاريخ.",
         recommend_if={"q": "LB_AGG", "includes_any": ["WALKING", "STANDING"]}),
    dict(code="SIT_TO_STAND", name_ar="النهوض من الجلوس", name_en="Sit-to-stand", category="function", result_type="value",
         sides=False, unit="ثانية لـ5 مرات", provocative=False, indication="قياس وظيفي قابل للمقارنة.",
         safety="مرافقة عند خطر السقوط.", position="كرسي ثابت بلا مساند", steps="5 مرات بأسرع ما يمكن بأمان؛ سجّل الزمن والأعراض.",
         positive="قيمة كمية.", limits="يتأثر بقوة الطرف السفلي والتوازن."),
    dict(code="NEURO_MYOTOMES", name_ar="القوة العضلية حسب القطع العصبية", name_en="Myotomes (MRC 0–5)", category="neuro",
         result_type="grade", sides=True, provocative=False, sublevels=LEVELS_MYO,
         indication="ألم ممتد للطرف أو أعراض عصبية.", safety="لا قيود خاصة.", position="جلوس/استلقاء",
         steps="قارن الجهتين لكل مجموعة عضلية؛ سجّل الدرجة 0–5 أو «لم يُفحص».",
         positive="ضعف ثابت مقارنة بالجهة الأخرى.", limits="الألم قد يحد من الجهد؛ وثّق ذلك. لا تُختزل النتيجة بكلمة «طبيعي».",
         recommend_if={"any": [{"q": "LB_DISTRIBUTION", "in": ["THIGH", "BELOW_KNEE", "FOOT", "BUTTOCK"]},
                               {"q": "LB_NEURO_SYMPTOMS", "includes_any": ["NUMBNESS", "TINGLING", "WEAKNESS", "GAIT", "BALANCE"]}]}),
    dict(code="NEURO_DERMATOMES", name_ar="الإحساس حسب القطع الجلدية", name_en="Dermatomes (light touch)", category="neuro",
         result_type="sensory", sides=True, provocative=False, sublevels=LEVELS_DERM,
         indication="ألم ممتد للطرف أو تنميل.", safety="لا قيود خاصة.", position="استلقاء",
         steps="لمس خفيف مقارنة بالجهة الأخرى لكل منطقة.",
         positive="نقص/غياب/زيادة إحساس ثابت.", limits="تداخل القطع الجلدية كبير بين الأشخاص.",
         recommend_if={"any": [{"q": "LB_DISTRIBUTION", "in": ["THIGH", "BELOW_KNEE", "FOOT", "BUTTOCK"]},
                               {"q": "LB_NEURO_SYMPTOMS", "includes_any": ["NUMBNESS", "TINGLING", "WEAKNESS"]}]}),
    dict(code="NEURO_REFLEXES", name_ar="المنعكسات الوترية", name_en="Deep tendon reflexes", category="neuro",
         result_type="reflex", sides=True, provocative=False, sublevels=REFLEXES,
         indication="ألم ممتد للطرف أو أعراض عصبية.", safety="لا قيود خاصة.", position="جلوس",
         steps="قارن الجهتين؛ استخدم تقنية التعزيز عند الحاجة.",
         positive="نقص/غياب غير متماثل، أو منعكسات مشتدة (تستدعي تقييماً طبياً).",
         limits="غياب متماثل قد يكون طبيعياً لدى كبار السن.",
         recommend_if={"any": [{"q": "LB_DISTRIBUTION", "in": ["THIGH", "BELOW_KNEE", "FOOT"]},
                               {"q": "LB_NEURO_SYMPTOMS", "includes_any": ["NUMBNESS", "TINGLING", "WEAKNESS", "GAIT", "BALANCE"]}]}),
    dict(code="SLR", name_ar="رفع الساق المستقيمة", name_en="Straight Leg Raise (SLR)", category="neurodynamic",
         result_type="posneg", sides=True, unit="درجة", provocative=True,
         indication="ألم ممتد للساق (خصوصاً أسفل الركبة) أو أعراض جذرية محتملة.",
         safety="يُحجب في المسار الإسعافي أو عند احتمال كسر غير مستبعد أو بعد جراحة حديثة دون إذن.",
         position="استلقاء على الظهر", steps="ارفع الساق سلبياً والركبة مستقيمة؛ سجّل الزاوية عند ظهور الأعراض وما إذا تغيّرت بثني ظهر القدم.",
         positive="إعادة إنتاج ألم الساق المألوف للمريض (وليس شد الخلفية فقط) مع تغيره بالتحسيس.",
         limits="حساسية جيدة نسبياً ونوعية محدودة؛ نتيجة واحدة لا تؤكد اعتلال الجذر ولا تحدد المستوى.",
         blocked_by=["PROVOCATIVE_TESTS_BLOCKED", "SUSPECTED_FRACTURE", "SURGICAL_RESTRICTIONS_UNCLEAR"],
         recommend_if={"any": [{"q": "LB_DISTRIBUTION", "in": ["THIGH", "BELOW_KNEE", "FOOT"]},
                               {"q": "LB_NEURO_SYMPTOMS", "includes_any": ["NUMBNESS", "TINGLING", "WEAKNESS"]}]}),
    dict(code="SLUMP", name_ar="اختبار الانهيار (Slump)", name_en="Slump test", category="neurodynamic", result_type="posneg",
         sides=True, provocative=True,
         indication="ألم ممتد للطرف مع شك بحساسية عصبية ميكانيكية.",
         safety="يُحجب في المسار الإسعافي أو عند احتمال كسر غير مستبعد أو بعد جراحة حديثة دون إذن.",
         position="جلوس على حافة السرير", steps="انهيار الجذع ثم ثني الرقبة ثم بسط الركبة وثني ظهر القدم؛ ثم تحرير الرقبة للتفريق البنيوي.",
         positive="إعادة إنتاج الأعراض المألوفة التي تتغير مع التفريق البنيوي (تحرير الرقبة).",
         limits="يُقرأ مع الفحص العصبي والتاريخ؛ لا يحدد المستوى.",
         blocked_by=["PROVOCATIVE_TESTS_BLOCKED", "SUSPECTED_FRACTURE", "SURGICAL_RESTRICTIONS_UNCLEAR"],
         recommend_if={"any": [{"q": "LB_DISTRIBUTION", "in": ["BUTTOCK", "THIGH", "BELOW_KNEE", "FOOT"]}]}),
    dict(code="REPEATED_MOVEMENTS", name_ar="الحركات المتكررة", name_en="Repeated movement testing", category="mechanical",
         result_type="repeated", sides=False, provocative=True,
         indication="لتوثيق استجابة الأعراض لحركة متكررة محددة.",
         safety="يُحجب في المسار الإسعافي أو عند احتمال كسر أو قيود جراحية غير موثقة. أوقف عند انتشار محيطي متزايد.",
         position="حسب الحركة", steps="سجّل الأعراض قبل/بعد، الحركة المستخدمة، عدد التكرارات، والاستجابة.",
         positive="لا يوجد «إيجابي»؛ توثيق: تحسن/تفاقم/تمركز/انتشار محيطي/لا تغيير.",
         limits="الاستجابة لا تفرض اتجاهاً علاجياً على كل المرضى؛ القرار للمختص.",
         blocked_by=["PROVOCATIVE_TESTS_BLOCKED", "SUSPECTED_FRACTURE", "SURGICAL_RESTRICTIONS_UNCLEAR"]),
]

EQUIPMENT = [
    "BTL EMSELLA", "BTL-6000 TR-Therapy", "BTL-4000 Premium", "BTL-Vac II (جهاز 1)", "BTL-Vac II (جهاز 2)",
    "BTL-6000 Lymphastim", "R-GAIT", "R-FORCE ELITE (BTL-805-1)", "BTL Cryotherapy", "BTL-CPMotion K ELITE",
    "BTL-6000 High Intensity Laser 30W", "BTL-6000 FSWT", "R-Touch Lead", "BTL Super Inductive System Duo",
    "DRX-9000", "Kineo", "HUR Rehab Upright Bike", "HUR Rehab Treadmill 6700", "HUR Multifunction 5X",
]

OUTCOMES = [
    dict(code="NPRS_NOW", name_ar="شدة الألم الآن (0–10)", unit="/10", direction="lower_better", min=0, max=10, enabled=True),
    dict(code="NPRS_WORST_WEEK", name_ar="أشد ألم خلال الأسبوع (0–10)", unit="/10", direction="lower_better", min=0, max=10, enabled=True),
    dict(code="PSFS_ITEM", name_ar="نشاط خاص بالمريض: القدرة (0 لا يستطيع – 10 كما قبل المشكلة)", unit="/10",
         direction="higher_better", min=0, max=10, enabled=True, labelled=True,
         note="على نمط Patient-Specific Functional Scale. يُسجَّل لكل نشاط يحدده المريض بالاسم نفسه في كل نقطة قياس."),
    dict(code="WALK_TOL_MIN", name_ar="تحمّل المشي (دقيقة)", unit="دقيقة", direction="higher_better", min=0, max=600, enabled=True),
    dict(code="SIT_TOL_MIN", name_ar="تحمّل الجلوس (دقيقة)", unit="دقيقة", direction="higher_better", min=0, max=600, enabled=True),
    dict(code="FTF_CM", name_ar="مسافة الأصابع-الأرض بالانثناء (سم)", unit="سم", direction="lower_better", min=0, max=100, enabled=True),
    dict(code="STS5_SEC", name_ar="النهوض من الجلوس 5 مرات (ثانية)", unit="ثانية", direction="lower_better", min=0, max=300, enabled=True),
    dict(code="ODI", name_ar="مؤشر أوسويستري للإعاقة (ODI)", unit="%", direction="lower_better", min=0, max=100, enabled=False,
         note="غير مفعّل: يتطلب نسخة عربية مرخّصة ومصادقاً عليها وحق استخدام. يُفعَّل من الكتالوج بعد توفير الترخيص."),
    dict(code="RMDQ", name_ar="استبيان رولاند-موريس (RMDQ)", unit="/24", direction="lower_better", min=0, max=24, enabled=False,
         note="غير مفعّل: يتطلب نسخة عربية مرخّصة وحق استخدام."),
]


def catalog_rows():
    rows = []
    for t in TESTS:
        rows.append(("TEST", t["code"], t))
    from .device_programs import equipment_rows
    from .exercises import catalog_rows as exercise_rows
    for eq in equipment_rows():
        rows.append(("EQUIPMENT", eq["code"], eq))
    for ex in exercise_rows():
        rows.append(("EXERCISE", ex["code"], ex))
    for oc in OUTCOMES:
        rows.append(("OUTCOME", oc["code"], oc))
    return rows
