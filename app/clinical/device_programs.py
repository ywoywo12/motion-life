"""Device catalogue with the BUILT-IN PROGRAMS of each device, transcribed from the program lists
supplied by Motion Life (files: BTL-6000_TR-Therapy.pdf, BTL-6000_FSWT.pdf, BTL-6000_Lymphastim.pdf,
BTL-6000_High_Intensity_Laser_30_W.pdf, BTL_Super_Inductive_System_Duo.pdf, BTL-4000_Premium.pdf,
بروتوكولات ULTRASOUND.docx, بروتوكولات R-FORCE.docx).

What a "protocol" means here: the name of the preset program stored ON THE DEVICE (as written on its
screen) + an Arabic name. Parameters (intensity, frequency, time, dose) are those of the device preset /
manufacturer manual and are adjusted by the treating clinician; this system does NOT invent parameters.
Arabic names were cleaned up from the supplied files (PDF text extraction garbles some Arabic letters).
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent / "data"


def P(en, ar):
    return {"en": en, "ar": ar}


TR_THERAPY = [
    P("Achillodynia", "ألم وتر أخيل"), P("Analgesia", "تسكين الألم"), P("Arthritis – rheumatoid", "التهاب المفاصل الروماتويدي"),
    P("Arthrosis", "خشونة المفاصل"), P("Bechterew´s disease", "التهاب الفقار اللاصق (بختريف)"),
    P("Carpal tunnel syndrome", "متلازمة النفق الرسغي"), P("Cervicalgia", "ألم الرقبة"),
    P("Cervicobrachial syndrome", "المتلازمة العنقية العضدية"), P("Cervicocranial syndrome", "المتلازمة العنقية القحفية"),
    P("Coxalgia", "ألم الورك"), P("Coxarthrosis", "خشونة مفصل الورك"), P("Dupuytren's contracture", "تقفع دوبويتران"),
    P("Epicondylitis", "التهاب اللقيمة"), P("Frozen shoulder", "الكتف المتجمدة"), P("Gonalgia", "ألم الركبة"),
    P("Gonarthrosis", "خشونة مفصل الركبة"), P("Heel spur", "شوكة الكعب"), P("Impingement syndrome", "متلازمة الانحشار (الكتف)"),
    P("Lumbalgia", "ألم أسفل الظهر"), P("Lumbosacral syndrome", "المتلازمة القطنية العجزية"), P("Metatarsalgia", "ألم مشط القدم"),
    P("Muscle regeneration", "تجديد العضلات"), P("Muscle relaxation", "إرخاء العضلات"), P("Myalgia", "ألم عضلي"),
    P("Sacralgia", "ألم العجز"), P("Tendinitis", "التهاب الأوتار"), P("Thoracalgia", "ألم الظهر الصدري"),
    P("Trigger points – deep", "نقاط الزناد - عميقة"), P("Trigger points – superficial", "نقاط الزناد - سطحية"),
    P("Trophic improvement", "تحسين التغذية النسيجية"), P("Vertebral algic syndrome", "متلازمة الألم الفقري"),
]

FSWT = [
    P("Achillodynia", "ألم وتر أخيل"), P("Arthrosis of the big joints", "خشونة المفاصل الكبيرة"),
    P("Arthrosis of the small joints", "خشونة المفاصل الصغيرة"), P("Avascular necrosis", "النخر اللاوعائي"),
    P("Bone marrow edema syndrome (BMES)", "متلازمة وذمة نقي العظم"), P("Bursitis chronic", "التهاب الجراب المزمن"),
    P("Calcification", "التكلس"), P("Carpal tunnel", "النفق الرسغي"), P("Epicondylitis", "التهاب اللقيمة (مرفق التنس)"),
    P("Frozen shoulder", "الكتف المتجمدة"), P("Greater trochanteric pain syndrome", "متلازمة ألم المدور الكبير"),
    P("Heel spur", "شوكة الكعب"), P("Chronic scars", "الندبات المزمنة"), P("Impingement syndrome", "متلازمة الانحشار"),
    P("Leg ulcers", "قرح الساق"), P("Medial tibial stress syndrome", "متلازمة إجهاد الظنبوب الإنسي"),
    P("Metatarsalgia", "ألم مشط القدم"), P("Muscle relaxation", "إرخاء العضلات"), P("Myalgia", "ألم عضلي"),
    P("Osteochondritis dissecans", "التهاب العظم والغضروف السالخ"), P("Plantar fasciitis", "التهاب اللفافة الأخمصية"),
    P("Pseudoarthrosis", "المفصل الكاذب (عدم التحام العظم)"), P("Spasticity", "الشناج (التشنج العصبي)"),
    P("Stress fracture healing", "التئام الكسور الإجهادية"), P("Tendinopathy", "اعتلال الأوتار"),
    P("Trigger points deep", "نقاط الزناد العميقة"), P("Wound healing", "التئام الجروح"),
]

LYMPHASTIM = [
    # Beauty / Aesthetic / Wellness
    P("Cellulite", "السيلوليت"), P("Detoxification", "إزالة السموم"), P("Heavy legs syndrome", "متلازمة ثقل الساقين"),
    P("Improvement in skin trophic", "تحسين تغذية الجلد"), P("Lipoedema", "الوذمة الشحمية"),
    P("Postliposuction care", "العناية بعد شفط الدهون"), P("Reconvalescence", "مرحلة النقاهة"), P("Regeneration", "التجديد"),
    P("Tenalgia - lower limbs", "ألم الأوتار - الأطراف السفلية"), P("Tenalgia - upper limbs", "ألم الأوتار - الأطراف العلوية"),
    P("Varicose veins prevention", "الوقاية من الدوالي"),
    # Medical
    P("Acrocyanosis - lower limbs", "زرقة الأطراف - السفلية"), P("Acrocyanosis - upper limbs", "زرقة الأطراف - العلوية"),
    P("Algodistrophic syndrome - lower limbs", "متلازمة الحثل المؤلم - الأطراف السفلية"),
    P("Algodistrophic syndrome - upper limbs", "متلازمة الحثل المؤلم - الأطراف العلوية"),
    P("Arthrosis - lower limbs", "خشونة المفاصل - الأطراف السفلية"), P("Arthrosis - upper limbs", "خشونة المفاصل - الأطراف العلوية"),
    P("Carpal Tunnel Syndrome - upper limbs", "متلازمة النفق الرسغي - الأطراف العلوية"),
    P("Diabetic angiopathy", "اعتلال الأوعية السكري"), P("Gout, holarthritis", "النقرس، التهاب المفاصل المتعدد"),
    P("Chronic oedemas", "الوذمات المزمنة"), P("Ischemic disease of lower limbs", "نقص التروية في الأطراف السفلية"),
    P("Neuropathy, Neuralgia", "اعتلال الأعصاب، ألم العصب"), P("Obesity - lower limbs", "السمنة - الأطراف السفلية"),
    P("Obesity - upper limbs", "السمنة - الأطراف العلوية"), P("Oncology", "الأورام (بإشراف طبي)"),
    P("Posttraumatic care - lower limbs", "رعاية ما بعد الإصابة - الأطراف السفلية"),
    P("Posttraumatic care - upper limbs", "رعاية ما بعد الإصابة - الأطراف العلوية"),
    P("Raynaud's syndrome - upper limbs", "متلازمة رينو - الأطراف العلوية"),
    P("Repair of poorly performed MLD", "تصحيح تصريف لمفاوي يدوي أُجري بشكل خاطئ"),
    P("Trophic disorders of skin - lower limbs", "اضطرابات تغذية الجلد - الأطراف السفلية"),
    P("Trophic disorders of skin - upper limbs", "اضطرابات تغذية الجلد - الأطراف العلوية"),
    P("Venous insufficiency", "القصور الوريدي المزمن"),
]

HIL = [
    P("Achilles tendonitis", "التهاب وتر أخيل"), P("Acne", "حب الشباب"), P("Ankle distortion", "التواء الكاحل"),
    P("Anterior tibial syndrome", "متلازمة قصبة الساق الأمامية"), P("Arthritis of the hand", "التهاب مفاصل اليد"),
    P("Arthrosis", "خشونة المفاصل"), P("Burns", "الحروق (تأهيل الأنسجة)"), P("Bursitis", "التهاب الجراب"),
    P("Carpal tunnel syndrome", "متلازمة النفق الرسغي"), P("Cervical pain", "ألم الرقبة"), P("Contusion", "الكدمات والرضوض"),
    P("Distortion", "الالتواء"), P("Dorsalgia", "ألم الظهر العلوي/الأوسط"), P("Dupuytren's contracture", "تقفع دوبويتران"),
    P("Eczema", "الأكزيما"), P("Edema reduction", "تقليل الوذمة"), P("Epicondylitis", "التهاب اللقيمة"),
    P("Facial nerve paresis", "ضعف العصب الوجهي"), P("Heel spur", "شوكة الكعب"), P("Hip joint arthrosis", "خشونة مفصل الورك"),
    P("Impingement syndrome", "متلازمة الانحشار"), P("Knee arthrosis", "خشونة الركبة"), P("Knee distortion", "التواء الركبة"),
    P("Lumbosacral syndrome", "المتلازمة القطنية العجزية"), P("Metatarsalgia", "ألم مشط القدم"), P("Muscle relaxation", "إرخاء العضلات"),
    P("Muscle strain", "الشد العضلي"), P("Nerve repair", "إصلاح الأعصاب"), P("Onychomycosis", "فطريات الأظافر"),
    P("Open wound", "جرح مفتوح"), P("Osgood-Schlatter disease", "داء أوسغود-شلاتر"), P("Pain relief", "تخفيف الألم"),
    P("Painful shoulder", "الكتف المؤلمة"), P("Patellar tendinopathy", "اعتلال الوتر الرضفي"),
    P("Plantar fasciitis", "التهاب اللفافة الأخمصية"), P("Postherpetic neuralgia", "ألم العصب التالي للهربس"), P("Scar", "الندبة"),
    P("Tarsal tunnel syndrome", "متلازمة النفق الرصغي (القدم)"), P("Tendinopathy", "اعتلال الأوتار"),
    P("Tendovaginitis", "التهاب غمد الوتر"), P("Tinnitus - ear canal", "طنين الأذن - القناة السمعية"),
    P("Tinnitus - proc. mastoideus", "طنين الأذن - النتوء الخشائي"),
]

SIS_DUO = [
    P("Achillodynia", "ألم وتر أخيل"), P("Analgesia – acute", "تسكين الألم - حاد"), P("Analgesia – chronic", "تسكين الألم - مزمن"),
    P("Analgesia – subacute", "تسكين الألم - تحت الحاد"), P("Arthritis – rheumatoid", "التهاب المفاصل الروماتويدي"),
    P("Arthrosis – acute", "خشونة المفاصل - حاد"), P("Arthrosis – chronic", "خشونة المفاصل - مزمن"),
    P("Bechterew´s disease", "التهاب الفقار اللاصق (بختريف)"), P("Breathing enhancement", "تحسين التنفس (الصدر والأضلاع)"),
    P("Bursitis – acute", "التهاب الجراب - حاد"), P("Bursitis – chronic", "التهاب الجراب - مزمن"),
    P("Calcification – extraarticular", "التكلس خارج المفصل"), P("Carpal tunnel syndrome", "متلازمة النفق الرسغي"),
    P("Cervicalgia – acute", "ألم الرقبة - حاد"), P("Cervicalgia – chronic", "ألم الرقبة - مزمن"),
    P("Circulation and trophic improvement – acute", "تحسين الدورة الدموية والتغذية - حاد"),
    P("Circulation and trophic improvement – chronic", "تحسين الدورة الدموية والتغذية - مزمن"),
    P("Distortion", "الالتواء"), P("Distortion – acute", "الالتواء - حاد"), P("Distortion – subacute", "الالتواء - تحت الحاد"),
    P("Epicondylitis", "التهاب اللقيمة"), P("Fracture", "الكسر"), P("Gonalgia – acute", "ألم الركبة - حاد"),
    P("Gonalgia – chronic", "ألم الركبة - مزمن"), P("Haematoma", "الورم الدموي"),
    P("Healing enhancement – acute", "تعزيز الالتئام - حاد"), P("Healing enhancement – chronic", "تعزيز الالتئام - مزمن"),
    P("Heel spur", "شوكة الكعب"), P("Impingement syndrome", "متلازمة الانحشار (الكتف)"),
    P("Intra-articular degeneration", "التنكس داخل المفصل"), P("Intra-articular injury", "إصابة داخل المفصل"),
    P("Joint mobilization", "تحريك المفصل"), P("Joint stabilization", "تثبيت المفصل"),
    P("Lumbosacral syndrome – acute", "المتلازمة القطنية العجزية - حاد"), P("Lumbosacral syndrome – chronic", "المتلازمة القطنية العجزية - مزمن"),
    P("Muscle atrophy – prevention", "الوقاية من ضمور العضلات"), P("Muscle regeneration", "تجديد العضلات"),
    P("Muscle relaxation", "إرخاء العضلات"), P("Muscle strain", "إجهاد/شد العضلات"), P("Muscle strengthening", "تقوية العضلات"),
    P("Muscle strengthening – dynamic", "تقوية العضلات - ديناميكي"), P("Myalgia – acute", "ألم عضلي - حاد"),
    P("Myalgia – chronic", "ألم عضلي - مزمن"), P("Nerve repair", "إعادة تأهيل الأعصاب"), P("Neuralgia", "الألم العصبي"),
    P("Neuromodulation – analgesia", "التعديل العصبي - تسكين"), P("Neuromodulation – strengthening", "التعديل العصبي - تقوية"),
    P("Neuropathy", "اعتلال الأعصاب"), P("Osgood-Schlatter disease", "داء أوسغود-شلاتر"), P("Pelvic floor therapy", "علاج قاع الحوض"),
    P("Post-stroke therapy", "العلاج بعد السكتة الدماغية"), P("Pre-rehabilitation training", "التدريب قبل التأهيل"),
    P("Prevention of venous thromboembolism", "الوقاية من الانصمام الخثاري الوريدي"),
    P("Scar – chronic", "ندبة - مزمنة"), P("Scar – subacute", "ندبة - تحت حادة"), P("Slipped disc", "انزلاق القرص"),
    P("Spasticity reduction", "تقليل الشناج"), P("Spinal muscles spasm", "تشنج عضلات العمود الفقري"),
    P("Swelling reduction", "تقليل التورم"), P("Tarsal tunnel syndrome", "متلازمة النفق الرصغي (القدم)"),
    P("Tendinopathy", "اعتلال الأوتار"), P("Thoracalgia – acute", "ألم الظهر الصدري - حاد (يطبق على الظهر)"),
    P("Thoracalgia – chronic", "ألم الظهر الصدري - مزمن (يطبق على الظهر)"), P("Trigger point", "نقطة زناد (موضع التحفيز وفوق المنطقة)"),
    P("Trigger points", "نقاط الزناد (في موضعها)"),
]

ULTRASOUND = [
    P("Adnexitis - post-inflammatory changes", "التهاب الملحقات - تغيرات ما بعد الالتهاب"),
    P("Algodystrophy - Sudeck's syndrome - post surgery", "الحثل الانعكاسي (سوديك) - بعد الجراحة"),
    P("Analgesia - acute", "تسكين الألم - حاد"), P("Analgesia - chronic", "تسكين الألم - مزمن"), P("Arthritis", "التهاب المفاصل"),
    P("Arthritis - subaqual application", "التهاب المفاصل - تطبيق تحت الماء"), P("Arthrosis – acute", "خشونة المفاصل - حاد"),
    P("Arthrosis - chronic", "خشونة المفاصل - مزمن"), P("Bechterew´s disease", "التهاب الفقار اللاصق (بختريف)"),
    P("Bursitis - acute", "التهاب الجراب - حاد"), P("Bursitis - chronic", "التهاب الجراب - مزمن"),
    P("Capsulitis - acute", "التهاب المحفظة - حاد"), P("Capsulitis - chronic", "التهاب المحفظة - مزمن"),
    P("Carpal tunnel syndrome - subaqual", "متلازمة النفق الرسغي - تحت الماء"),
    P("Circulation and trophic improvement", "تحسين الدورة الدموية والتغذية النسيجية"),
    P("Contusion – acute", "الكدمة - حاد"), P("Contusion - acute - subaqual application", "الكدمة - حاد - تحت الماء"),
    P("Contusion – chronic", "الكدمة - مزمن"), P("Distorsion – acute", "الالتواء - حاد"), P("Distorsion – chronic", "الالتواء - مزمن"),
    P("Distorsion - subaqual application", "الالتواء - تحت الماء"), P("Dupuytren's contracture", "تقفع دوبويتران"),
    P("Endometritis - post-inflammatory changes", "التهاب بطانة الرحم - تغيرات ما بعد الالتهاب"),
    P("Epicondylitis – acute", "التهاب اللقيمة - حاد"), P("Epicondylitis – chronic", "التهاب اللقيمة - مزمن"),
    P("Epicondylitis - subaqual application", "التهاب اللقيمة - تحت الماء"), P("Fibromyalgia", "الألم العضلي الليفي"),
    P("Frozen shoulder", "الكتف المتجمدة"), P("Haematoma – chronic", "الورم الدموي - مزمن"),
    P("Haematoma – subacute", "الورم الدموي - تحت الحاد"), P("Heel spur", "شوكة الكعب"),
    P("Heel spur - subaqual application", "شوكة الكعب - تحت الماء"), P("Lumbalgia", "ألم أسفل الظهر"),
    P("Muscle relaxation", "إرخاء العضلات"), P("Muscle strain", "الشد العضلي"),
    P("Parametritis - post-inflammatory changes", "التهاب جارات الرحم - تغيرات ما بعد الالتهاب"), P("Sacralgia", "ألم العجز"),
    P("Scar", "الندبة"), P("Scar – cheloid", "الندبة الجدرية (الجدرة)"), P("Swelling reduction", "تخفيف التورم"),
    P("Tendinitis – acute", "التهاب الأوتار - حاد"), P("Tendinitis - acute - subaqual application", "التهاب الأوتار - حاد - تحت الماء"),
    P("Tendinitis – chronic", "التهاب الأوتار - مزمن"), P("Tendinitis – subacute", "التهاب الأوتار - تحت الحاد"),
    P("Tendinitis - subacute - subaqual application", "التهاب الأوتار - تحت الحاد - تحت الماء"),
    P("Tendovaginitis – acute", "التهاب غمد الوتر - حاد"), P("Tendovaginitis - acute - subaqual application", "التهاب غمد الوتر - حاد - تحت الماء"),
    P("Tendovaginitis – chronic", "التهاب غمد الوتر - مزمن"), P("Tendovaginitis – subacute", "التهاب غمد الوتر - تحت الحاد"),
    P("Tendovaginitis - subacute - subaqual application", "التهاب غمد الوتر - تحت الحاد - تحت الماء"),
    P("Trigger points – deep", "نقاط الزناد - عميقة"), P("Trigger points – superficial", "نقاط الزناد - سطحية"),
    P("Trismus", "تشنج عضلات الفك (الضزز)"), P("Trochanteritis – acute", "التهاب المدور - حاد"),
    P("Trochanteritis – chronic", "التهاب المدور - مزمن"), P("Tubal sterility", "العقم الأنبوبي (بإشراف طبي)"),
    P("Vasoneurosis - acrocyanosis and Raynaud’s disease", "العصاب الوعائي - زرقة الأطراف وداء رينو"),
]

R_FORCE = [
    P("Cardio – difficult", "إعادة تأهيل القلب - صعب"), P("Cardio – easy", "إعادة تأهيل القلب - سهل"),
    P("Cardio – medium", "إعادة تأهيل القلب - متوسط"),
    P("Elderly: difficult level – endurance", "كبار السن: صعب - تحمّل"), P("Elderly: easy level – endurance", "كبار السن: سهل - تحمّل"),
    P("Elderly: easy level – strength", "كبار السن: سهل - قوة"), P("Elderly: medium level – endurance", "كبار السن: متوسط - تحمّل"),
    P("Elderly: medium level – strength", "كبار السن: متوسط - قوة"),
    P("Neurorehabilitation: mild condition – endurance", "تأهيل عصبي: حالة خفيفة - تحمّل"),
    P("Neurorehabilitation: mild condition – jogging", "تأهيل عصبي: حالة خفيفة - هرولة"),
    P("Neurorehabilitation: mild condition – strength", "تأهيل عصبي: حالة خفيفة - قوة"),
    P("Neurorehabilitation: moderate condition", "تأهيل عصبي: حالة متوسطة"),
    P("Neurorehabilitation: severe condition", "تأهيل عصبي: حالة شديدة"),
    P("Orthopaedic: acute condition", "تأهيل عظمي: حالة حادة"), P("Orthopaedic: chronic condition – endurance", "تأهيل عظمي: مزمن - تحمّل"),
    P("Orthopaedic: chronic condition – jogging", "تأهيل عظمي: مزمن - هرولة"),
    P("Orthopaedic: chronic condition – strength", "تأهيل عظمي: مزمن - قوة"), P("Orthopaedic: subacute condition", "تأهيل عظمي: تحت حاد"),
    P("Sport: running for beginner", "رياضة: الجري للمبتدئين"), P("Sport: uphill running", "رياضة: الجري صعوداً"),
    P("Sport: uphill walking", "رياضة: المشي صعوداً"), P("Sport: workout – endurance", "رياضة: تمرين تحمّل"),
    P("Sport: workout – speed", "رياضة: تمرين سرعة"), P("Sport: workout – strength", "رياضة: تمرين قوة"),
    P("Weight loss: obesity - easy", "خسارة الوزن: سمنة - سهل"), P("Weight loss: obesity – medium", "خسارة الوزن: سمنة - متوسط"),
    P("Weight loss: overweight – difficult", "خسارة الوزن: زيادة وزن - صعب"),
    P("Weight loss: overweight – easy", "خسارة الوزن: زيادة وزن - سهل"),
    P("Weight loss: overweight – medium", "خسارة الوزن: زيادة وزن - متوسط"),
]


def _btl4000():
    rows = json.loads((_DATA / "btl4000_electro.json").read_text(encoding="utf-8"))
    return [{"en": r["en"], "ar": r["ar"], "no": r["no"], "group": r["group_ar"]} for r in rows]


# code, model name (as on the device), Arabic description, category, program list, source file
DEVICES = [
    ("EQ01", "BTL EMSELLA", "كرسي تقوية قاع الحوض بالحقل الكهرومغناطيسي", "electromagnetic", None, None),
    ("EQ02", "BTL-6000 TR-Therapy", "جهاز TR (تيكار) - العلاج بالترددات الراديوية", "radiofrequency", TR_THERAPY, "BTL-6000_TR-Therapy.pdf"),
    ("EQ03", "BTL-4000 Premium — Electrotherapy", "جهاز العلاج الكهربائي", "electrotherapy", "BTL4000", "BTL-4000_Premium.pdf"),
    ("EQ20", "BTL-4000 Premium — Ultrasound", "جهاز الموجات فوق الصوتية", "ultrasound", ULTRASOUND, "بروتوكولات ULTRASOUND.docx"),
    ("EQ04", "BTL-Vac II (جهاز 1)", "جهاز الشفط (إلكترودات الشفط)", "electrotherapy", None, None),
    ("EQ05", "BTL-Vac II (جهاز 2)", "جهاز الشفط (إلكترودات الشفط)", "electrotherapy", None, None),
    ("EQ06", "BTL-6000 Lymphastim", "جهاز التصريف اللمفاوي بالضغط", "compression", LYMPHASTIM, "BTL-6000_Lymphastim.pdf"),
    ("EQ07", "R-GAIT", "جهاز تدريب المشي الروبوتي", "robotics", None, None),
    ("EQ08", "R-FORCE ELITE (BTL-805-1)", "سير متحرك بتخفيف وزن الجسم", "robotics", R_FORCE, "بروتوكولات R-FORCE.docx"),
    ("EQ09", "BTL Cryotherapy", "العلاج بالتبريد", "thermal", None, None),
    ("EQ10", "BTL-CPMotion K ELITE", "جهاز الحركة السلبية المستمرة للركبة/الورك (CPM)", "cpm", None, None),
    ("EQ11", "BTL-6000 High Intensity Laser 30W", "ليزر عالي الشدة", "laser", HIL, "BTL-6000_High_Intensity_Laser_30_W.pdf"),
    ("EQ12", "BTL-6000 FSWT", "الموجات الصادمة المركّزة", "shockwave", FSWT, "BTL-6000_FSWT.pdf"),
    ("EQ13", "R-Touch Lead", "جهاز تأهيل الطرف العلوي التفاعلي", "robotics", None, None),
    ("EQ14", "BTL-6000 Super Inductive System DUO", "التحفيز المغناطيسي عالي الشدة", "electromagnetic", SIS_DUO, "BTL_Super_Inductive_System_Duo.pdf"),
    ("EQ15", "DRX-9000", "جهاز الشد الفقري (Decompression)", "traction", None, None),
    ("EQ16", "Kineo", "جهاز التمارين والتقييم المحوسب (Kineo)", "exercise", None, None),
    ("EQ17", "HUR Rehab Upright Bike", "دراجة تأهيل ثابتة", "exercise", None, None),
    ("EQ18", "HUR Rehab Treadmill 6700", "سير مشي تأهيلي", "exercise", None, None),
    ("EQ19", "HUR Multifunction 5X", "جهاز تمارين القوة متعدد الوظائف", "exercise", None, None),
]

CATEGORY_AR = {"electromagnetic": "كهرومغناطيسي", "radiofrequency": "ترددات راديوية", "electrotherapy": "علاج كهربائي",
               "ultrasound": "فوق صوتي", "compression": "ضغط/تصريف", "robotics": "روبوتي/تأهيل حركي", "thermal": "حراري/تبريد",
               "cpm": "حركة سلبية", "laser": "ليزر", "shockwave": "موجات صادمة", "traction": "شد", "exercise": "تمارين"}


def equipment_rows():
    rows = []
    for code, model, ar, cat, progs, src in DEVICES:
        if progs == "BTL4000":
            progs = _btl4000()
        programs = []
        for i, p in enumerate(progs or [], 1):
            programs.append({"code": f"{code}-P{i:03d}", "en": p["en"], "ar": p["ar"], **({"no": p["no"]} if "no" in p else {}),
                             **({"group": p["group"]} if "group" in p else {})})
        rows.append({
            "code": code, "name": model, "name_ar": ar, "category": cat, "category_ar": CATEGORY_AR[cat],
            "programs": programs, "source": src,
            "status_note": "برامج الجهاز من ملف المركز" if programs else "لا توجد قائمة برامج مرفقة — تُدخل الإعدادات يدوياً",
            "info": ("اختيار البرنامج يحدد الإعداد المسبق المخزّن في الجهاز. الشدة/الزمن/الجرعة يضبطها المختص حسب دليل الشركة "
                     "والحالة، مع مراجعة الموانع."),
        })
    return rows
