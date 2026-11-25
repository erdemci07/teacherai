"""Sınırlı geometri teorem kaydı (TA-008 §13). Her teorem önkoşul ve sonuç taşır.

Teorem adının açıklamada geçmesi teoremin uygulanabildiğini göstermez: ``geometry.analyze`` önkoşulları
modelin *kullanılabilir* olgularında (metinde verilen, şekilde işaretli, türetilmiş, yardımcı çizimle tanımlanmış)
arar. Yalnız ``executable`` teoremler belirlenimci denklem üretir; diğerleri yalnız tanınır ve ``not_checked``
kalır. Evrensel otomatik ispat yapılmaz.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theorem:
    id: str
    name_tr: str
    preconditions_tr: tuple[str, ...]
    conclusion_tr: str
    words: tuple[str, ...]  # öğrenci açıklamasında tanıma (yalnız önkoşul denetimini tetikler)
    executable: bool
    knowledge_id: str | None = None


THEOREMS: dict[str, Theorem] = {item.id: item for item in [
    Theorem("triangle_angle_sum", "Üçgenin iç açıları toplamı", ("üç nokta bir üçgen oluşturur",),
            "İç açıların toplamı 180°'dir.", ("iç açılar toplamı", "180"), True, "geo.triangle-angle-sum"),
    Theorem("exterior_angle", "Dış açı teoremi", ("üçgenin bir kenarı uzatılmış", "uzatma doğrusal"),
            "Dış açı, komşu olmayan iki iç açının toplamına eşittir.", ("dış açı",), True, "geo.exterior-angle"),
    Theorem("pythagorean", "Pisagor teoremi", ("üçgen", "dik açı metinde verilmiş veya şekilde işaretli"),
            "Hipotenüsün karesi dik kenarların kareleri toplamına eşittir.", ("pisagor", "hipotenüs"), True,
            "geo.pythagorean"),
    Theorem("pythagorean_converse", "Pisagor teoreminin karşıtı", ("üç kenar uzunluğu bilinir",),
            "a² + b² = c² ise c'nin karşısındaki açı diktir.", ("karşıtı",), True, "geo.pythagorean-converse"),
    Theorem("triangle_inequality", "Üçgen eşitsizliği", ("üç kenar uzunluğu",),
            "Her kenar diğer iki kenarın toplamından küçük, farkının mutlak değerinden büyüktür.",
            ("üçgen eşitsizliği",), True, "geo.triangle-inequality"),
    Theorem("isosceles", "İkizkenar üçgen", ("iki kenarın eşitliği metinde verilmiş veya işaretli",),
            "Eşit kenarların karşısındaki açılar eşittir.", ("ikizkenar",), True, "geo.isosceles"),
    Theorem("congruence", "Eşlik ölçütleri (KAK, AKA, KKK)", ("karşılıklı köşe eşlemesi açık",),
            "Karşılıklı kenar ve açılar eşittir.", ("eş üçgen", "eşlik"), True, "geo.congruence-criteria"),
    Theorem("similarity", "Benzerlik", ("karşılıklı köşe eşlemesi açık", "açı-açı veya kenar oranları"),
            "Karşılıklı kenarların oranı eşittir.", ("benzer", "benzerlik"), True, "geo.similarity"),
    Theorem("angle_bisector", "Açıortay teoremi", ("açıortay metinde verilmiş veya işaretli",),
            "Açıortay karşı kenarı komşu kenarlar oranında böler.", ("açıortay",), False, "geo.angle-bisector"),
    Theorem("triangle_area", "Üçgenin alanı", ("taban ve o tabana ait yükseklik",),
            "Alan = taban × yükseklik / 2.", ("alan",), True, "geo.triangle-area"),
    Theorem("parallel_angles", "Paralel doğrularda açılar", ("paralellik verilmiş", "kesen doğru"),
            "Yöndeş ve iç ters açılar eşittir.", ("yöndeş", "iç ters", "paralel"), False, "geo.parallel-angles"),
    Theorem("quadrilateral_properties", "Özel dörtgen özellikleri", ("dörtgenin türü metinde verilmiş",),
            "Türüne göre kenar/açı/köşegen özellikleri.", ("paralelkenar", "dikdörtgen", "eşkenar dörtgen", "yamuk"),
            False, "geo.quadrilaterals"),
    Theorem("inscribed_angle", "Çevre açı", ("açının köşesi çember üzerinde", "aynı yayı gören merkez açı"),
            "Çevre açı aynı yayı gören merkez açının yarısıdır.", ("çevre açı", "merkez açı"), False,
            "geo.inscribed-angle"),
    Theorem("tangent_radius", "Teğet–yarıçap dikliği", ("teğet metinde verilmiş",),
            "Teğet değme noktasındaki yarıçapa diktir.", ("teğet",), True, "geo.tangent-radius"),
    Theorem("coordinate_distance", "İki nokta arası uzaklık", ("koordinatlar verilmiş",),
            "d = √((x₂−x₁)² + (y₂−y₁)²).", ("uzaklık",), True, "geo.coordinate-distance"),
    Theorem("midpoint", "Orta nokta", ("orta nokta metinde verilmiş",),
            "Orta nokta uç noktalardan eşit uzaklıktadır; koordinatları ortalamadır.", ("orta nokta",), True,
            "geo.midpoint"),
    Theorem("slope", "Eğim ve doğrular", ("koordinatlar verilmiş",),
            "Paralel doğruların eğimleri eşit, dik doğruların eğimleri çarpımı −1'dir (dikey doğru hariç).",
            ("eğim",), True, "geo.slope"),
]}


def mentioned(text: str) -> list[Theorem]:
    lowered = (text or "").replace("İ", "i").replace("I", "ı").lower()
    return [item for item in THEOREMS.values() if any(word in lowered for word in item.words)]
