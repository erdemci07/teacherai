"""TA-008 matematik yetenek matrisi: *gerçekte* ne yapıldığının açık kaydı (hedef mimari değil).

Sütunlar:
- recognition: konu tanıma kanıtı — ``structural`` (AST), ``lexical`` (taksonomi takma adı), ``none``.
- representation: yapılandırılmış temsil (sözleşme) veya ``none``.
- local_solver: yalıtılmış işçide çalışan belirlenimci çözücü veya ``none``.
- verification: ``independent`` (kesin, bağımsız), ``partial`` (bir bölümü), ``ai_assisted_only``, ``unsupported``.
- runtime: ``live`` (ders akışında kaynak ifadeler ayrıştığında), ``model`` (yalnız sağlayıcı yapılandırılmış model
  önerdiğinde), ``offline`` (yalnız çevrimdışı/regresyon), ``none``.
- evaluation: bağımsız öğretmen anahtarıyla değerlendirme durumu (TA-008'de hiçbir konu değerlendirilmedi).
"""

from __future__ import annotations

ROWS = [
    # konu, tanıma, temsil, yerel çözücü, doğrulama, çalışma zamanı, not
    ("Doğal/tam/rasyonel sayılar, kesirler", "lexical", "none", "mathai.targets:constant", "independent", "live",
     "Değişkensiz ifadenin kesin değeri; sözel sayı problemi modelsiz kalır."),
    ("Bölünebilme, asal çarpan, EBOB–EKOK", "lexical", "none", "none", "ai_assisted_only", "none", "Belirlenimci çözücü yok."),
    ("Üslü ve köklü ifadeler", "structural", "none", "mathai.targets:constant", "independent", "live", "Sabit ifadeler; değişkenli köklü denklem aşağıda."),
    ("Mutlak değer", "lexical", "none", "mathematics.sets:solve_equation", "independent", "live", "Durumların birleşimi çözüm kümesiyle karşılaştırılır."),
    ("Oran, orantı, yüzde", "lexical", "WordProblemModel", "mathematics.word_problems:analyze", "partial", "model",
     "Model tutarlılığı bağımsız; modelin soruya sadakati kısmi (değerler metinde mi)."),
    ("Sayı kümeleri ve aralıklar", "lexical", "SolutionSetView", "mathematics.sets:view", "independent", "live", "Açık/kapalı uç, kopuk aralık, tekil dışlama."),
    ("Cebirsel ifadeler, özdeşlikler, çarpanlara ayırma", "lexical", "none", "none", "partial", "live",
     "Adım denkliği denetlenir; çarpanlara ayırmanın 'en sade' olduğu denetlenmez."),
    ("Doğrusal denklemler", "structural", "SolutionSetView", "mathematics.sets:solve_equation", "independent", "live",
     "Sonsuz/boş çözüm, adım denkliği, x'e bölmede kök kaybı."),
    ("Doğrusal eşitsizlikler", "structural", "SolutionSetView", "mathematics.sets:solve_inequality", "independent", "live",
     "Negatifle çarpmada yön, işareti bilinmeyen çarpan uyarısı."),
    ("Denklem sistemleri", "lexical", "WordProblemModel", "mathematics.word_problems:analyze", "partial", "model",
     "Tek/sonsuz/çözümsüz ayrımı model üzerinden."),
    ("İkinci derece denklemler", "lexical", "SolutionSetView, AlternativePath", "mathematics.sets:solve_equation, mathematics.alternatives:quadratic",
     "independent", "live", "Gerçel/karmaşık ayrımı; üç belirlenimci alternatif yol."),
    ("Polinomlar", "lexical", "none", "none", "partial", "live", "Polinom denklemi çözüm kümesi; bölme/kalan denetimi yok."),
    ("Rasyonel ve köklü denklemler", "lexical", "SolutionSetView", "mathematics.sets:solve_equation", "independent", "live",
     "Tanım kümesi özgün ifadeden; yabancı kök elenir."),
    ("Üstel ve logaritmik ifadeler", "lexical", "none", "mathematics.sets:solve_equation", "partial", "live",
     "Logaritma argümanı tanım kümesi; çözücü kapalı biçim bulamazsa unsupported."),
    ("Fonksiyon tanımı, tanım/değer kümesi", "lexical", "GraphSegment", "mathematics.functions:analyze", "independent", "live",
     "Tanımsız noktada grafik bölünür; değer kümesi hesaplanmaz."),
    ("Bileşke ve ters fonksiyon", "lexical", "none", "mathematics.functions:compose, inverse", "independent", "offline",
     "Birebirlik denetimli; ders akışında soru kalıbı yok."),
    ("Grafik dönüşümleri, parçalı fonksiyon", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var; belirlenimci denetim yok."),
    ("Kökler, kesişimler, işaret aralıkları, tepe noktası", "lexical", "none", "mathematics.functions:sign_intervals, intersections, vertex",
     "independent", "offline", "Yerel çözücü; ders akışında yalnız y = f(x) kaynak ifadesiyle."),
    ("Sözel problemler (yaş, hareket, iş, karışım, kâr–zarar)", "lexical", "WordProblemModel", "mathematics.word_problems:analyze",
     "partial", "model", "Doğru modelin doğru çözümü ≠ sorunun doğrulanmış çözümü; sadakat kısmi."),
    ("Veri ve tablo yorumu", "lexical", "none", "mathematics.probability:table_totals_consistent", "partial", "offline", "Tablo toplam tutarlılığı."),
    ("Açılar, üçgenler, eşlik, benzerlik", "lexical", "GeometryModel", "mathematics.geometry:analyze", "independent", "model",
     "Yalnız kullanılabilir olgular; belirli/belirsiz/çok değerli/tutarsız; köşe eşlemesi."),
    ("Açıortay, kenarortay, yükseklik", "lexical", "Construction", "mathematics.geometry:analyze", "partial", "model",
     "Yardımcı çizim tanımı denetlenir; açıortay teoremi yürütülmez."),
    ("Dörtgenler, çokgenler", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var; teorem yürütülmez."),
    ("Çember ve daire", "lexical", "GeometryModel", "mathematics.geometry:analyze", "partial", "model", "Teğet–yarıçap dikliği yürütülür; çevre açı yürütülmez."),
    ("Alan, çevre, hacim", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var."),
    ("Analitik geometri (uzaklık, orta nokta, eğim)", "lexical", "GeometryModel", "mathematics.geometry:analyze", "independent", "model",
     "Koordinatlardan kesin uzaklık; çakışık nokta saptanır."),
    ("Trigonometri", "structural", "none", "mathematics.trig:solve_in_interval, exact_value", "independent", "offline",
     "Derece/radyan ayrımı; aralıkta bütün kökler. Ders akışında aralıksız denklem 'periyodik' kısmi."),
    ("Diziler", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var."),
    ("Sayma, permütasyon, kombinasyon", "lexical", "none", "mathematics.probability:permutations, combinations", "independent", "offline", "Sınırlı kesin sayım."),
    ("Olasılık (koşullu, bağımsız, ayrık)", "lexical", "none", "mathematics.probability:draw_space", "independent", "offline",
     "Eş olasılık açık varsayım; örnek uzayı sınırlı."),
    ("İstatistik", "lexical", "none", "mathematics.probability:describe", "independent", "offline", "Kesin rasyonel aritmetik."),
    ("Limit ve süreklilik", "lexical", "none", "mathematics.calculus:limit, continuous_at", "independent", "offline", "Tek/iki yönlü ayrımı."),
    ("Türev ve ekstremum", "structural", "none", "mathematics.calculus:critical_points, global_extrema", "independent", "offline",
     "Türev sıfır ≠ ekstremum; ders akışında yalnız yöntem denetimi (türev yasağı)."),
    ("İntegral ve alan", "structural", "none", "mathematics.calculus:definite, check_antiderivative", "independent", "offline",
     "İşaretli integral ≠ alan; genelleştirilmiş integral ayrımı."),
]


def rows() -> list[dict]:
    keys = ("topic", "recognition", "representation", "local_solver", "verification", "runtime", "note")
    return [dict(zip(keys, row)) for row in ROWS]
