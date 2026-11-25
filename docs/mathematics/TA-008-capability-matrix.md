# TA-008 matematik yetenek matrisi

Bu dosya `python -m scripts.math_matrix` ile üretilir; elle düzenlenmez. CI `--check` uygular.

Matris *gerçekte uygulanan* yeteneği gösterir; hedef mimari değildir. Hiçbir konu bağımsız öğretmen anahtarıyla değerlendirilmedi (değerlendirme: **yok**). `runtime`: `live` ders akışında kaynak ifadeler ayrıştığında, `model` yalnız sağlayıcı yapılandırılmış model önerdiğinde, `offline` yalnız çevrimdışı/regresyonda.

| Konu | Tanıma | Temsil | Yerel çözücü | Doğrulama | Çalışma zamanı | Değerlendirme | Not |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Doğal/tam/rasyonel sayılar, kesirler | lexical | none | `mathai.targets:constant` | independent | live | yok | Değişkensiz ifadenin kesin değeri; sözel sayı problemi modelsiz kalır. |
| Bölünebilme, asal çarpan, EBOB–EKOK | lexical | none | `none` | ai_assisted_only | none | yok | Belirlenimci çözücü yok. |
| Üslü ve köklü ifadeler | structural | none | `mathai.targets:constant` | independent | live | yok | Sabit ifadeler; değişkenli köklü denklem aşağıda. |
| Mutlak değer | lexical | none | `mathematics.sets:solve_equation` | independent | live | yok | Durumların birleşimi çözüm kümesiyle karşılaştırılır. |
| Oran, orantı, yüzde | lexical | WordProblemModel | `mathematics.word_problems:analyze` | partial | model | yok | Model tutarlılığı bağımsız; modelin soruya sadakati kısmi (değerler metinde mi). |
| Sayı kümeleri ve aralıklar | lexical | SolutionSetView | `mathematics.sets:view` | independent | live | yok | Açık/kapalı uç, kopuk aralık, tekil dışlama. |
| Cebirsel ifadeler, özdeşlikler, çarpanlara ayırma | lexical | none | `none` | partial | live | yok | Adım denkliği denetlenir; çarpanlara ayırmanın 'en sade' olduğu denetlenmez. |
| Doğrusal denklemler | structural | SolutionSetView | `mathematics.sets:solve_equation` | independent | live | yok | Sonsuz/boş çözüm, adım denkliği, x'e bölmede kök kaybı. |
| Doğrusal eşitsizlikler | structural | SolutionSetView | `mathematics.sets:solve_inequality` | independent | live | yok | Negatifle çarpmada yön, işareti bilinmeyen çarpan uyarısı. |
| Denklem sistemleri | lexical | WordProblemModel | `mathematics.word_problems:analyze` | partial | model | yok | Tek/sonsuz/çözümsüz ayrımı model üzerinden. |
| İkinci derece denklemler | lexical | SolutionSetView, AlternativePath | `mathematics.sets:solve_equation, mathematics.alternatives:quadratic` | independent | live | yok | Gerçel/karmaşık ayrımı; üç belirlenimci alternatif yol. |
| Polinomlar | lexical | none | `none` | partial | live | yok | Polinom denklemi çözüm kümesi; bölme/kalan denetimi yok. |
| Rasyonel ve köklü denklemler | lexical | SolutionSetView | `mathematics.sets:solve_equation` | independent | live | yok | Tanım kümesi özgün ifadeden; yabancı kök elenir. |
| Üstel ve logaritmik ifadeler | lexical | none | `mathematics.sets:solve_equation` | partial | live | yok | Logaritma argümanı tanım kümesi; çözücü kapalı biçim bulamazsa unsupported. |
| Fonksiyon tanımı, tanım/değer kümesi | lexical | GraphSegment | `mathematics.functions:analyze` | independent | live | yok | Tanımsız noktada grafik bölünür; değer kümesi hesaplanmaz. |
| Bileşke ve ters fonksiyon | lexical | none | `mathematics.functions:compose, inverse` | independent | offline | yok | Birebirlik denetimli; ders akışında soru kalıbı yok. |
| Grafik dönüşümleri, parçalı fonksiyon | lexical | none | `none` | ai_assisted_only | none | yok | Bilgi girdisi var; belirlenimci denetim yok. |
| Kökler, kesişimler, işaret aralıkları, tepe noktası | lexical | none | `mathematics.functions:sign_intervals, intersections, vertex` | independent | offline | yok | Yerel çözücü; ders akışında yalnız y = f(x) kaynak ifadesiyle. |
| Sözel problemler (yaş, hareket, iş, karışım, kâr–zarar) | lexical | WordProblemModel | `mathematics.word_problems:analyze` | partial | model | yok | Doğru modelin doğru çözümü ≠ sorunun doğrulanmış çözümü; sadakat kısmi. |
| Veri ve tablo yorumu | lexical | none | `mathematics.probability:table_totals_consistent` | partial | offline | yok | Tablo toplam tutarlılığı. |
| Açılar, üçgenler, eşlik, benzerlik | lexical | GeometryModel | `mathematics.geometry:analyze` | independent | model | yok | Yalnız kullanılabilir olgular; belirli/belirsiz/çok değerli/tutarsız; köşe eşlemesi. |
| Açıortay, kenarortay, yükseklik | lexical | Construction | `mathematics.geometry:analyze` | partial | model | yok | Yardımcı çizim tanımı denetlenir; açıortay teoremi yürütülmez. |
| Dörtgenler, çokgenler | lexical | none | `none` | ai_assisted_only | none | yok | Bilgi girdisi var; teorem yürütülmez. |
| Çember ve daire | lexical | GeometryModel | `mathematics.geometry:analyze` | partial | model | yok | Teğet–yarıçap dikliği yürütülür; çevre açı yürütülmez. |
| Alan, çevre, hacim | lexical | none | `none` | ai_assisted_only | none | yok | Bilgi girdisi var. |
| Analitik geometri (uzaklık, orta nokta, eğim) | lexical | GeometryModel | `mathematics.geometry:analyze` | independent | model | yok | Koordinatlardan kesin uzaklık; çakışık nokta saptanır. |
| Trigonometri | structural | none | `mathematics.trig:solve_in_interval, exact_value` | independent | offline | yok | Derece/radyan ayrımı; aralıkta bütün kökler. Ders akışında aralıksız denklem 'periyodik' kısmi. |
| Diziler | lexical | none | `none` | ai_assisted_only | none | yok | Bilgi girdisi var. |
| Sayma, permütasyon, kombinasyon | lexical | none | `mathematics.probability:permutations, combinations` | independent | offline | yok | Sınırlı kesin sayım. |
| Olasılık (koşullu, bağımsız, ayrık) | lexical | none | `mathematics.probability:draw_space` | independent | offline | yok | Eş olasılık açık varsayım; örnek uzayı sınırlı. |
| İstatistik | lexical | none | `mathematics.probability:describe` | independent | offline | yok | Kesin rasyonel aritmetik. |
| Limit ve süreklilik | lexical | none | `mathematics.calculus:limit, continuous_at` | independent | offline | yok | Tek/iki yönlü ayrımı. |
| Türev ve ekstremum | structural | none | `mathematics.calculus:critical_points, global_extrema` | independent | offline | yok | Türev sıfır ≠ ekstremum; ders akışında yalnız yöntem denetimi (türev yasağı). |
| İntegral ve alan | structural | none | `mathematics.calculus:definite, check_antiderivative` | independent | offline | yok | İşaretli integral ≠ alan; genelleştirilmiş integral ayrımı. |

## Regresyon derlemi

`apps/api/tests/fixtures/mathematics/regression.json`: 61 sentetik vaka (olumlu, olumsuz, sınır ve çekimser). Geçen: 61/61.

| Alan | Vaka | Geçen |
| --- | --- | --- |
| algebra | 16 | 16 |
| calculus | 8 | 8 |
| foundations | 3 | 3 |
| functions | 6 | 6 |
| geometry | 9 | 9 |
| probability | 5 | 5 |
| statistics | 1 | 1 |
| strategy | 2 | 2 |
| trigonometry | 5 | 5 |
| word_problems | 6 | 6 |

Sentetik derlem başarısı gerçek model doğruluğu değildir.
