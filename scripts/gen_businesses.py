"""Stage 6: generate the fictional businesses used for TRAINING (spec/train_businesses.json).

They share the schema of spec/businesses.json, but none of the four test businesses (or
their names) appear here: the test then measures whether the model reads the business
info in the prompt rather than remembering it. Deterministic (fixed seed).

Run: uv run python scripts/gen_businesses.py
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spec" / "train_businesses.json"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# vertical: (type in English, name pattern, customers, hours options, services, extra policies)
# services: (id, name, short_name, price range SAR, duration min)
VERTICALS = {
    "dental": ("dental clinic", "عيادة {} لطب الأسنان", "unknown", ["clinic_evening", "clinic_day"], [
        ("checkup", "كشف واستشارة", "الكشف", (80, 150), 20), ("cleaning", "تنظيف أسنان", "التنظيف", (180, 300), 45),
        ("filling", "حشوة تجميلية", "الحشوة", (250, 450), 60), ("extraction", "خلع ضرس", "الخلع", (150, 350), 30),
        ("whitening", "تبييض", "التبييض", (900, 1600), 90)], []),
    "derma": ("dermatology and skin care clinic", "عيادة {} للجلدية", "unknown", ["clinic_evening", "clinic_day"], [
        ("consult", "استشارة جلدية", "الاستشارة", (150, 300), 20), ("facial", "تنظيف بشرة عميق", "تنظيف البشرة", (250, 450), 60),
        ("laser", "جلسة ليزر إزالة شعر", "الليزر", (300, 700), 45), ("peel", "تقشير كيميائي", "التقشير", (350, 600), 40)], []),
    "physio": ("physiotherapy center", "مركز {} للعلاج الطبيعي", "unknown", ["clinic_day", "clinic_evening"], [
        ("assessment", "تقييم أولي", "التقييم", (150, 250), 45), ("session", "جلسة علاج طبيعي", "الجلسة", (200, 350), 60),
        ("massage", "مساج علاجي", "المساج", (180, 300), 45)], []),
    "eye": ("eye clinic", "عيادة {} للعيون", "unknown", ["clinic_evening", "clinic_day"], [
        ("vision", "فحص نظر", "فحص النظر", (80, 150), 20), ("full_exam", "فحص عيون شامل", "الفحص الشامل", (250, 400), 45),
        ("lenses", "فحص وتركيب عدسات", "العدسات", (200, 350), 40)], []),
    "vet": ("veterinary clinic", "عيادة {} البيطرية", "unknown", ["clinic_day", "clinic_evening"], [
        ("vet_checkup", "كشف بيطري", "الكشف", (100, 200), 30), ("vaccine", "تطعيم", "التطعيم", (120, 250), 20),
        ("grooming", "قص أظافر وتنظيف", "التنظيف", (80, 150), 30)], ["pets: cats and dogs only"]),
    "barber": ("men's barber shop", "حلاق {}", "men only", ["daily_late"], [
        ("haircut", "حلاقة شعر", "الحلاقة", (40, 90), 30), ("beard", "تحديد لحية", "اللحية", (25, 50), 20),
        ("full", "حلاقة شعر ولحية", "الحلاقة الكاملة", (60, 120), 45), ("beard_dye", "صبغة لحية", "الصبغة", (40, 80), 30)], []),
    "salon": ("women's beauty salon", "صالون {}", "women only", ["salon"], [
        ("cut", "قص شعر", "القص", (100, 200), 45), ("blowdry", "سشوار", "السشوار", (70, 150), 40),
        ("color", "صبغة شعر", "الصبغة", (300, 600), 120), ("mani", "مناكير", "المناكير", (60, 120), 40),
        ("pedi", "بدكير", "البدكير", (80, 150), 45), ("evening_makeup", "مكياج سهرة", "المكياج", (350, 700), 90)], []),
    "spa": ("women's spa", "سبا {}", "women only", ["salon"], [
        ("relax", "مساج استرخاء", "المساج", (250, 450), 60), ("hammam", "حمام مغربي", "الحمام المغربي", (200, 400), 75),
        ("face", "تنظيف بشرة", "تنظيف البشرة", (180, 350), 60)], []),
    "gym": ("gym", "نادي {} الرياضي", "unknown", ["gym"], [
        ("trial", "زيارة تجريبية يوم", "الزيارة التجريبية", (30, 80), 90), ("pt", "حصة مدرب شخصي", "حصة المدرب", (120, 250), 60),
        ("yoga", "حصة يوغا", "اليوغا", (60, 120), 60)], ["separate hours for women: see front desk"]),
    "car_wash": ("car wash", "مغسلة {}", "unknown", ["daily_long"], [
        ("outside", "غسيل خارجي", "الغسيل الخارجي", (25, 40), 20), ("full", "غسيل داخلي وخارجي", "الغسيل الكامل", (50, 80), 40),
        ("polish", "تلميع", "التلميع", (200, 350), 120), ("engine", "تنظيف مكينة", "تنظيف المكينة", (60, 120), 40)],
        ["prices for sedans; SUVs add {suv} SAR"]),
    "car_service": ("car maintenance center", "مركز {} لصيانة السيارات", "unknown", ["workshop"], [
        ("oil", "تغيير زيت", "تغيير الزيت", (120, 250), 30), ("diagnosis", "فحص كمبيوتر", "الفحص", (100, 200), 30),
        ("alignment", "ترصيص وميزان", "الترصيص", (80, 150), 45), ("brakes", "تغيير فحمات فرامل", "الفرامل", (200, 400), 60)],
        ["parts priced separately"]),
    "restaurant": ("Saudi restaurant (table reservations)", "مطعم {}", "unknown", ["restaurant"], [
        ("t2", "طاولة لشخصين", "طاولة لشخصين", (0, 0), 90), ("t4", "طاولة 4 أشخاص", "طاولة لـ4", (0, 0), 90),
        ("family", "جلسة عائلية خاصة (حتى 10 أشخاص)", "الجلسة العائلية", (150, 300), 120)],
        ["family section and singles section", "reservations hold {hold} minutes"]),
    "cafe": ("specialty coffee cafe (table reservations)", "مقهى {}", "unknown", ["cafe"], [
        ("table", "طاولة", "الطاولة", (0, 0), 90), ("outdoor", "جلسة خارجية", "الجلسة الخارجية", (0, 0), 90),
        ("group", "حجز مجموعة (حتى 8)", "حجز المجموعة", (80, 150), 120)], ["reservations hold {hold} minutes"]),
    "studio": ("photography studio", "استوديو {} للتصوير", "unknown", ["workshop"], [
        ("portrait", "جلسة تصوير شخصي", "التصوير الشخصي", (250, 500), 60), ("family_shoot", "تصوير عائلي", "التصوير العائلي", (400, 800), 90),
        ("passport", "صور جواز", "صور الجواز", (30, 60), 15)], []),
    "tailor": ("men's tailor", "خياط {} للثياب", "men only", ["workshop"], [
        ("thobe", "تفصيل ثوب (موعد مقاسات)", "التفصيل", (200, 450), 30), ("alter", "تعديل ثوب", "التعديل", (30, 80), 20)],
        ["delivery of new thobes in 10 days"]),
    "cleaning": ("home cleaning company (home visits)", "شركة {} لتنظيف المنازل", "unknown", ["office"], [
        ("apartment", "تنظيف شقة", "تنظيف الشقة", (250, 450), 240), ("villa", "تنظيف فيلا", "تنظيف الفيلا", (600, 1200), 480),
        ("sofa", "تنظيف كنب", "تنظيف الكنب", (150, 300), 120)], ["visits need the full address"]),
    "ac": ("air conditioner maintenance (home visits)", "{} لصيانة المكيفات", "unknown", ["office"], [
        ("ac_clean", "تنظيف مكيف سبليت", "تنظيف المكيف", (80, 150), 60), ("ac_fix", "فحص وإصلاح", "الفحص", (100, 200), 60),
        ("gas", "تعبئة فريون", "تعبئة الفريون", (150, 300), 45)], ["spare parts priced separately"]),
    "tutoring": ("tutoring center", "مركز {} التعليمي", "unknown", ["tutoring"], [
        ("math", "حصة رياضيات", "حصة الرياضيات", (100, 200), 60), ("english", "حصة إنجليزي", "حصة الإنجليزي", (100, 200), 60),
        ("level", "اختبار تحديد مستوى", "تحديد المستوى", (0, 50), 30)], []),
    "escape": ("escape room", "{} لغرف الهروب", "unknown", ["entertainment"], [
        ("room4", "غرفة لـ 4 أشخاص", "غرفة الأربعة", (200, 320), 60), ("room6", "غرفة لـ 6 أشخاص", "غرفة الستة", (280, 420), 60)], []),
    "hall": ("event hall (daily bookings)", "قاعة {} للمناسبات", "unknown", ["office"], [
        ("small_hall", "قاعة صغيرة (حتى 50)", "القاعة الصغيرة", (2500, 5000), 300), ("big_hall", "قاعة كبيرة (حتى 200)", "القاعة الكبيرة", (8000, 15000), 300)],
        ["30% deposit to confirm"]),
}
HOURS = {
    "clinic_evening": {d: (None if d in ("Fri", "Sat") else "16:00-23:00") for d in DAYS},
    "clinic_day": {d: (None if d == "Fri" else "09:00-21:00") for d in DAYS},
    "salon": {d: ("16:00-23:00" if d == "Fri" else "12:00-22:00") for d in DAYS},
    "daily_late": {d: ("15:00-24:00" if d == "Fri" else "10:00-24:00") for d in DAYS},
    "daily_long": {d: "07:00-23:00" for d in DAYS},
    "gym": {d: ("14:00-24:00" if d == "Fri" else "06:00-24:00") for d in DAYS},
    "workshop": {d: (None if d == "Fri" else "08:00-20:00") for d in DAYS},
    "restaurant": {d: "13:00-25:00" for d in DAYS},
    "cafe": {d: "07:00-25:00" for d in DAYS},
    "office": {d: (None if d == "Fri" else "09:00-18:00") for d in DAYS},
    "tutoring": {d: (None if d in ("Fri", "Sat") else "14:00-21:00") for d in DAYS},
    "entertainment": {d: ("14:00-25:00" if d in ("Thu", "Fri") else "16:00-24:00") for d in DAYS},
}
NAME_WORDS = ["النخبة", "الريم", "الواحة", "السنا", "اللؤلؤة", "الأفق", "الندى", "الماسة", "الصفوة", "الجود",
              "البيان", "الوفاء", "الإتقان", "الأصالة", "الريادة", "المسك", "النسيم", "الشروق", "الخزامى", "العليا",
              "الرونق", "الغيمة", "القمة", "الياسمين", "الهدى", "المدى", "الفجر", "النور", "الرمال", "النخيل",
              "الزهور", "السحاب", "المرجان", "الفيروز", "الديوان", "الكرم", "الروابي", "الضياء", "الأمل", "السلام"]
CITIES = {  # city: districts
    "الرياض": ["حي النرجس", "حي الياسمين", "حي العليا", "حي الملز", "حي السويدي"],
    "جدة": ["حي الشاطئ", "حي السلامة", "حي الحمراء", "حي النعيم"],
    "الدمام": ["حي الفيصلية", "حي الشاطئ الغربي"], "الخبر": ["حي العقربية", "حي الحزام الذهبي"],
    "مكة": ["حي العزيزية", "حي الشوقية"], "المدينة": ["حي قباء", "حي العزيزية"], "أبها": ["حي المنسك"],
    "الطائف": ["حي الشهداء"], "بريدة": ["حي الصفراء"], "حائل": ["حي النقرة"], "تبوك": ["حي المروج"],
    "جازان": ["حي الروضة"], "نجران": ["حي الفيصلية"], "الأحساء": ["حي المزروعية"],
}
PERSONAS = {"female": ["سارة", "ريما", "لمى", "هيا", "جود", "منى", "أمل", "دانة", "شهد", "نوف"],
            "male": ["عبدالعزيز", "فيصل", "ماجد", "تركي", "خالد", "سلطان", "راكان", "بدر", "نايف", "يزيد"]}
TEST_NAMES = ["ابتسامة المروج", "لمسة ورد", "البريق", "سفرة الديرة"]


def fmt_hours(schedule: dict) -> str:
    groups: dict[str | None, list[str]] = {}
    for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
        groups.setdefault(schedule[d], []).append(d)
    order = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    parts = []
    for spec, days in groups.items():
        runs, run = [], [days[0]]  # consecutive days become one range: Sun-Thu, Sat
        for d in days[1:]:
            if order.index(d) == order.index(run[-1]) + 1:
                run.append(d)
            else:
                runs.append(run)
                run = [d]
        runs.append(run)
        label = "daily" if len(days) == 7 else ", ".join(
            r[0] if len(r) == 1 else f"{r[0]}-{r[-1]}" if len(r) > 2 else f"{r[0]}, {r[1]}" for r in runs)
        if spec is None:
            parts.append(f"{label} closed")
        else:
            a, b = spec.split("-")
            parts.append(f"{label} {a}-{'00:00' if b == '24:00' else '01:00' if b == '25:00' else b}")
    return "; ".join(parts)


def main() -> None:
    rng = random.Random(2026)
    words = NAME_WORDS[:]
    rng.shuffle(words)
    cities = list(CITIES)
    businesses = []
    for n, (key, (btype, pattern, customers, hour_opts, services, extra)) in enumerate(
            sorted(VERTICALS.items()) * 2):
        name = pattern.format(words.pop())
        assert not any(t in name for t in TEST_NAMES)
        city = cities[n % len(cities)]
        district = rng.choice(CITIES[city])
        gender = "female" if customers == "women only" else "male" if customers == "men only" else rng.choice(["female", "male"])
        schedule = HOURS[rng.choice(hour_opts)]
        cancel_h = rng.choice([2, 3, 6, 12, 24])
        pay = rng.choice(["cash, mada, Apple Pay", "mada, Apple Pay, Tabby", "cash, mada", "mada, Apple Pay, STC Pay"])
        policies = [f"cancel or reschedule free up to {cancel_h} hours before", f"payment: {pay}"]
        policies += [p.format(suv=rng.choice([10, 15, 20]), hold=rng.choice([10, 15, 20])) for p in extra]
        if key in ("dental", "derma", "eye", "physio"):
            policies.append(rng.choice(["insurance: not accepted", "insurance: accepted (Bupa, Tawuniya)"]))
        bid = f"train_{key}_{n // len(VERTICALS) + 1}"
        businesses.append({
            "id": bid, "name": name, "type": btype, "city": city,
            "address": f"{district}، {city}", "map_link": f"https://maps.example.com/{bid.replace('_', '-')}",
            "hours": fmt_hours(schedule), "policies": policies,
            "services": [{"id": sid, "name": sname, "short_name": short,
                          "price_sar": rng.randrange(lo, hi + 1, 5) if hi else 0, "duration_min": dur}
                         for sid, sname, short, (lo, hi), dur in services],
            "assistant": {"name": rng.choice(PERSONAS[gender]), "gender": gender},
            "customers": customers, "schedule": schedule,
        })
    OUT.write_text(json.dumps(businesses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.name}: {len(businesses)} businesses, {len({b['type'] for b in businesses})} types, "
          f"{len({b['city'] for b in businesses})} cities")


if __name__ == "__main__":
    main()
