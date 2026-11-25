"""TA-008/TA-008B matematik yetenek matrisi: *gerçekte* ne yapıldığının açık kaydı (hedef mimari değil).

Sütunlar:
- recognition: konu tanıma kanıtı — ``structural`` (AST), ``lexical`` (taksonomi takma adı), ``none``.
- representation: yapılandırılmış temsil (sözleşme) veya ``none``.
- local_solver: yalıtılmış işçide çalışan belirlenimci çözücü veya ``none``.
- verification: ``independent`` (kesin, bağımsız), ``partial`` (bir bölümü), ``ai_assisted_only``, ``unsupported``.
- runtime: ``live`` (ders akışında kaynak ifadeler ayrıştığında), ``model`` (yalnız sağlayıcı yapılandırılmış model
  önerdiğinde), ``offline`` (yalnız çevrimdışı/regresyon), ``none``.
- evaluation: bağımsız öğretmen anahtarıyla değerlendirme durumu (TA-008 ve TA-008B'de hiçbir konu değerlendirilmedi).

TA-008B: canlı kontroller maddi çelişki (yanlış istenen cevap, eksik çözüm, geçersiz dönüşüm) bulursa ders doğrulanmış
sayılmaz ve tek sınırlı düzeltme turu çalışır. Uzmanlık raporu çekirdek durumu hiçbir zaman güçlendirmez.
"""

from __future__ import annotations

ROWS = [
    # konu, tanıma, temsil, yerel çözücü, doğrulama, çalışma zamanı, not
    ("Doğal/tam/rasyonel sayılar, kesirler", "lexical", "none", "mathai.targets:constant", "independent", "live",
     "Değişkensiz ifadenin kesin değeri; sözel sayı problemi modelsiz kalır."),
    ("Bölünebilme, asal çarpan, EBOB–EKOK", "lexical", "none", "none", "ai_assisted_only", "none", "Belirlenimci çözücü yok."),
    ("Üslü ve köklü ifadeler", "structural", "none", "mathai.targets:constant", "independent", "live", "Sabit ifadeler; değişkenli köklü denklem aşağıda."),
    ("Mutlak değer", "lexical", "none", "mathematics.sets:solve_equation", "independent", "live", "Durum dallarının (ardışık case adımları dahil) birleşimi önceki kümeyle karşılaştırılır; tek dal eksik dal değildir."),
    ("Oran, orantı, yüzde", "lexical", "WordProblemModel", "mathematics.word_problems:analyze", "partial", "model",
     "Model tutarlılığı bağımsız; sadakat kısmi: değer metinde ve alıntıyla bağlı mı; ilişkilerin anlamı doğrulanmaz."),
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
     "Tanım kümesi sadeleştirmeden önceki AST'den (x/x, x⁰, x⁻¹·x); yabancı kök elenmesi kayıp sayılmaz."),
    ("Üstel ve logaritmik ifadeler", "lexical", "none", "mathematics.sets:solve_equation", "partial", "live",
     "Logaritma argümanı tanım kümesi; çözücü kapalı biçim bulamazsa unsupported."),
    ("Fonksiyon tanımı, tanım/değer kümesi", "lexical", "GraphSegment", "mathematics.functions:analyze, evaluate", "independent", "live",
     "Delik (açık daire) ve asimptot ayrımı; f(x) tanımlı ve f(a) istenirse f(a) bağımsız hesaplanır; değer kümesi hesaplanmaz."),
    ("Bileşke ve ters fonksiyon", "lexical", "none", "mathematics.functions:compose, inverse", "independent", "offline",
     "Birebirlik denetimli; ders akışında soru kalıbı yok."),
    ("Grafik dönüşümleri, parçalı fonksiyon", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var; belirlenimci denetim yok."),
    ("Tepe noktası (en büyük/en küçük değer)", "structural", "none", "mathematics.functions:vertex", "independent", "live",
     "Yalnız y = f(x) ikinci derece kaynak ifadesi ve en büyük/en küçük hedefi; olmayan uç tür reddedilir."),
    ("Kökler, kesişimler, işaret aralıkları", "lexical", "none", "mathematics.functions:sign_intervals, intersections",
     "independent", "offline", "Hedef kalıbı yalnız sözcükle tanınabildiği için ders akışına bağlanmadı."),
    ("Sözel problemler (yaş, hareket, iş, karışım, kâr–zarar)", "lexical", "WordProblemModel", "mathematics.word_problems:analyze",
     "partial", "model", "Doğru modelin doğru çözümü ≠ sorunun doğrulanmış çözümü; aynı sembole çoklu kısıt; toplamda birim uyuşmazlığı; hedef ↔ son cevap."),
    ("Veri ve tablo yorumu", "lexical", "none", "mathematics.probability:table_totals_consistent", "partial", "offline", "Tablo toplam tutarlılığı."),
    ("Açılar, üçgenler, eşlik, benzerlik", "lexical", "GeometryModel", "mathematics.geometry:analyze", "independent", "model",
     "Olgu yalnız metin alıntısı, işaretli şekil, doğrulanmış türetme veya geçerli çizimle kısıt olur; doğrusal ≠ arada; hedef ↔ son cevap."),
    ("Açıortay, kenarortay, yükseklik", "lexical", "Construction", "mathematics.geometry:analyze", "partial", "model",
     "Çizim yalnız tanımından izleyen olguları kurar (yükseklik ayağı uzantıda olabilir; BH = HC kurulmaz); açıortay teoremi yürütülmez."),
    ("Dörtgenler, çokgenler", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var; teorem yürütülmez."),
    ("Çember ve daire", "lexical", "GeometryModel", "mathematics.geometry:analyze", "partial", "model", "Teğet–yarıçap dikliği yalnız çember, merkez ve değme noktası kuruluysa; çevre açı yürütülmez."),
    ("Alan, çevre, hacim", "lexical", "none", "none", "ai_assisted_only", "none", "Bilgi girdisi var."),
    ("Analitik geometri (uzaklık, orta nokta, eğim)", "lexical", "GeometryModel", "mathematics.geometry:analyze", "independent", "model",
     "Koordinatlardan kesin uzaklık; çakışık nokta saptanır."),
    ("Trigonometri", "structural", "none", "mathematics.trig:solve_in_interval, exact_value", "independent", "offline",
     "Derece/radyan ayrımı; aralıkta bütün kökler. Ders akışında aralıksız denklem 'periyodik' kısmi; derece işareti (°) ayrıştırılmaz."),
    ("Trigonometrik sabit ifadeler (radyan)", "structural", "none", "mathematics.expr", "independent", "live",
     "Değişkensiz istenen ifade kesin hesaplanır ve son cevapla karşılaştırılır."),
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
