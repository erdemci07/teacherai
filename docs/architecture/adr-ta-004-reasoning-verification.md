# ADR TA-004 — Çok disiplinli akıl yürütme, bilimsel doğrulama ve istenen hedef

Durum: kabul edildi (TA-004). Kod: `apps/api/app/features/reasoning/`, `features/mathai/targets.py`, sözleşmeler `features/education/{reasoning,science,lesson}.py`. Sonuçlar [TA-004 raporunda](../phase-reports/TA-004.md). Bu kayıt yalnızca çalışan kodu anlatır.

## 1. Sorun

TA-003 bir sorunun doğru okunduğunu sınar. Doğru okunmuş bir soruda bile iki ayrı hata kalıyordu:

1. **İstenen hedef.** MathAI, verilen denklemin çözümünü her sorunun cevabı sayıyordu. `x = 3` verilip `x + 2` sorulduğunda, önce-çöz stratejisiyle seçenekler sağlayıcıdan gizlendiği için seçenek uzlaştırması `3` değerini arıyor ve yanlış seçeneği (`A) 3`) seçebiliyordu.
2. **Alan eşitsizliği.** Fizik, kimya ve biyoloji (FKB) yalnızca temsil edilebiliyordu. Birim, tepkime, etiket veya deney verisi için hiçbir yerel denetim yoktu.

## 2. Kararlar

### 2.1 İstenen hedef (`AnswerTarget`, `TargetResolution`)

- Hedef, sağlayıcıdan bağımsız olarak `reasoning/target.py` içinde belirlenir. Kaynaklar: soru kökünün son soru cümlesindeki Türkçe kalıplar (kökler toplamı/çarpımı, kaç tane, en büyük/küçük, tam sayı, çözüm kümesi, aralık), bütünlük raporundaki `requested` rollü ifade, soru cümlesindeki sınırlı ifade parçası (`B − A kaçtır`) ve kaynakta açıkça işaretlenmiş bilinmeyen (`h = ?`, metin veya şekil etiketi). Sembol adları büyük/küçük harfe duyarlıdır.
- Hesaplanabilen alt küme şunlardır: değişken değeri, ifade değeri (toplam, fark, çarpım, oran), çözüm sayısı, kökler toplamı/çarpımı, çözüm kümesi, en küçük/en büyük (eşitsizlikte tam sayı dahil), tanımlardan yerine koyma (`A = …, B = …` için `B − A`), iki bilinmeyenli tek denklemde sabit oran (`2x = 3y` için `x/y`) ve çözülen değişkende değerlendirilebilen I/II/III öncül birleşimi. Diğer türler temsil edilir ama `unsupported` kalır.
- Katlı veya karmaşık kökte "kökler toplamı" Vieta ile gerçel çözüm kümesinden farklı olabilir. Bu durumda değer tahmin edilmez (`multiplicity_or_complex_roots`).
- `TargetResolution` şunları ayrı alanlarda tutar: verilen model, ara değerler, bağımsız değer, sağlayıcı önerisi ve rolü (`target` / `intermediate`), seçilen seçenek ve seçimin kökeni. Şema, bağımsız değer ve hedefe ait öneri yoksa `passed` sonucunu reddeder.
- Seçenek uzlaştırması artık değişken değerini değil, istenen hedefin değerini arar. Hedef çözülemezse seçenek değiştirilmez. Sorulan sembol modelde yoksa (`k kaçtır?`, verilen `x = 3`) hedef `unresolved` olur. Bu durumda `x` değerine bağlanılmaz.
- Son cevap kontrolü (`final_answer`) hedefe göre yapılır. Ara değeri son cevap olarak veren öneri `intermediate_not_requested` ile başarısız olur ve mevcut tek düzeltme turunu tetikler. Yeni döngü yoktur.

### 2.2 Dönüşüm doğruluğu (MathAI)

Mevcut SymPy işçisi yeniden yazılmadı; tüm yeni sembolik iş aynı yalıtılmış işçide çalışır.

- Kökler özgün denkleme konur. Paydayı sıfırlayan aday atılır ve `domain_restrictions` kaydedilir.
- Kare alma veya ifadeyle çarpma gibi tersinir olmayan bir adım çözüm kümesini genişletebilir. Bu, `nonreversible_superset` nedeniyle kabul edilir; v2'de `partially_checked` görünür. Fazla kök son cevapta kalırsa `extraneous_root` olarak adlandırılır.
- Çözüm kaybı `solution_lost` (ör. değişkenle bölme) olarak işaretlenir.
- Eşitsizlik adımlarında çözüm kümesi karşılaştırılır. Yön hatası, ters çevrilmiş ilişkinin kümesiyle doğrulanır (`inequality_direction`).
- Ardışık denklemler arasındaki işlem yalnızca kanıtlanabiliyorsa adlandırılır (`classify`): iki tarafa ekleme/çıkarma, çarpma/bölme, kare alma, değişkeni yalnız bırakma, açma/çarpanlara ayırma. Kanıtlanamazsa işlem `unknown` kalır.

### 2.3 LessonPlan v2 2.2.0

- `DerivationStepBlock`: `inputs/outputs/conclusions` (`EvidenceRef`), `operation` ile `operation_origin` (`deterministic | v1_step_type | fixture | unknown`), `method_ref`, varsayım, ön koşul ve anlatım referansı. Biyoloji gibi denklemsiz akıl yürütme `from/to` ifadesi gerektirmez. v1 adım türünden yalnızca anlamı açık olanlar eşlenir (`case`, `result`, `explanation`, `diagram_reference`, `graph_reference`). Uyarı adımı düz metin kalır.
- `VerificationReport.block_checks`: hedef blok, boyut, doğrulayıcı, sonuç, neden ve kanıt. Eşleme yalnızca var olan MathAI kimliklerini kullanır: `step_N_i` → ifade bloğu, `step_N` → adım, `final_answer` / `answer_choice` → cevap. Bloğa bağlanamayan kontrol `lesson` / `unmapped` kalır. Kontrolü olmayan adım `none:<id>` / `not_checked` olarak görünür. Şema şu durumları reddeder: müfredat, yöntem veya pedagojide `passed`; doğrulayıcısı olmayan sonuç; alan doğrulayıcısı olmadan `scientific: passed`; bilinen çelişki varken `calculation: passed`; tanımsız bloğa bağlı kontrol.
- `VerificationReport.target` (`TargetResolution`), `EducationalDraft.narration` (yalnızca sözleşme; düz metin, sıralı, var olan bloğa bağlı) ve `LessonPlanV2.problem` (`ScientificProblemModel`) eklendi.
- 2.0.0 ve 2.1.0 belgeleri geçerlidir ancak 2.2.0 alanlarını taşıyamaz. v2 saklanmaz; v1 yetkili kayıttan her istekte üretilir. TA-004 öncesi v1 dersleri hedefsiz ve işlem adı `unknown` olarak, dürüstçe projekte edilir.

### 2.4 Ortak bilimsel problem modeli ve kanıt

`ScientificProblemModel` alanları şunlardır: gözlem, varlık, ilişki, bilinen ve bilinmeyen nicelik, varsayım, kısıt, ilke referansı (`unreviewed`), aday model, hedef, şekil, grafik, tablo, deney, öncül ve belirsizlik. Kökenler `source_text | visual_reading | student_confirmed | background_knowledge | modeling_assumption | inferred | derived` olarak ayrıdır. Şemanın değişmezleri:

- Çıkarım ve türetim kanıt göstermelidir. Varsayım gözlem listesine yazılamaz.
- Bir okun anlamı görsel okumadan gelemez; yalnızca kaynak metin veya öğrenci onayı ona anlam verebilir.
- Farklı panellerdeki varlıklar arasında ilişki kurulamaz. Tanımsız kimliğe atıf reddedilir.
- Grafik noktaları yalnızca basılı değerlerden gelir. Eksen ölçeği ve başlangıcı açıkça verilmedikçe `unknown` kalır.

İlişki sözlüğü izin listesidir: `connected_to, contains, part_of, points_to, measured_at, labeled_as, precedes, increases, decreases, adjacent_to, acts_on`. Evrensel sahne grafiği yoktur.

### 2.5 Yerel denetleyiciler (`features/reasoning/`)

Hepsi saf Python'dur, SymPy ve sağlayıcı kullanmaz. `eval`, `exec` ve `sympify` yoktur; bunu bir test tarar.

| Modül | Kapsam |
| --- | --- |
| `units.py` | Açık birim tablosu, boyut, kesin dönüşüm. `C`, `M`, `l` belirsizdir; `Co` birim değildir. °C ötelemelidir; kütle ile ağırlık dönüştürülmez. `m/s` ≡ `m·s⁻¹` ≠ `m/s²`, `10⁻³` ≠ `10³`. `1,250` belirsizdir, `0,002` belirsiz değildir. |
| `formula.py` | Birimli skaler formülde yerine koyma. Bağlanmamış sembol varsayılmaz (`g`). Yalnız boyut uyumu `partially_checked` sayılır. Açık noktalarla grafik eğimi ve alanı. Tablo sütunlarında eksik hücre korunur. |
| `chemistry.py` | Büyük/küçük harfe duyarlı formül; katsayı, alt simge, yük ve hâl ayrıdır. Atom ve yük korunumu, en küçük tam sayılı denkleştirme (kesirli Gauss eleminasyonu; çözüm tek değilse `unsupported`), stokiyometri, sınırlayıcı tür, tam ayrışmada iyon miktarı ve tek elementli değişimde elektron alışverişi. `Fe2+` (ASCII) belirsizdir. Hidrat ve mekanizma desteklenmez. |
| `evidence.py` | Etiket–yapı tutarlılığı, `precedes` sırası, ok yönü ve anlamı, deney iddiaları (eğilim, nedensellik için kontrollü tasarım, `correlation_not_causation`, `confounded_comparison`, `no_variation`), ölçülen uç değer ve kesin optimum ayrımı, oran sabitliği, orantılı tahmin, öncül kutupluluğu ve birleşim eşleşmesi. |
| `sequence.py` | Yönü yazılmış DNA kalıbından mRNA ve kodon (baz eşleşmesi kuralı). |
| `narrative.py` | Cümle aralıkları ve açık "sayı + birim" nicelikleri. Özgün metin kısaltılmaz. |
| `materiality.py` (integrity) | Eski OCR notunun önemliliği. |

Öncül durumları ayrıdır: `supported`, `contradicted`, `not_decidable` (kaynak yetersiz) ve `unevaluated` (denetleyici yok). Denetleyicinin sınırı "kaynak desteklemiyor" sayılmaz. Değerlendirilmemiş öncül varsa birleşim uydurulmaz.

### 2.6 Eski OCR notları ve zorunlu görsel

- Serbest metin notu artık yapılandırılmış belirsizlik olsa da olmasa da sınıflandırılır. Kritik sayılması için üç koşul birlikte gerekir: şüphe ifadesi, kategori ve kaynakta o yapının bulunması. Anahtar kelime tek başına engel değildir. Aynı kategorideki yapılandırılmış belirsizlikle birleşir. TA-003 öncesi kayıtlar (`legacy`) geriye dönük engellenmez.
- Zorunlu görselin olguları yoksa önce metne bakılır. Metinde verilen bir ilişki varsa veya metin görsele atıf yapmadan veri içeriyorsa çözüm devam eder (`essential_visual_text_sufficient`). Değilse mevcut tek hedefli yeniden okuma, basılı olguları ister. Gelen olgu `visual_supplied_by_recheck` kanıtıyla eklenir; tek okumadır, doğrulama değildir. Olgu gelmezse yeni fotoğraf istenir. Ders, uydurulmuş şekil bilgisiyle üretilmez; bağlam `visual_evidence: missing` bildirir.

## 3. Çalışma zamanı ve çağrı politikası

Akış: Vision ve revizyon → bütünlük → `/lessons/generate` → mevcut tek ders çağrısı (bağlamda `answer_target` ipucu) → MathAI (hedef, adım, alan, seçenek) → yetkili v1 kayıt → v2 2.2.0 projeksiyonu.

- Yeni zorunlu sağlayıcı çağrısı yoktur; modelleme, çıkarım ve doğrulama yereldir.
- Hedef çelişkisi mevcut sınırlı düzeltme turunu kullanır. Mantıksal çağrı tavanı, kota, küresel bütçe ve idempotency değişmedi.
- FKB soruları hâlâ 422 `subject_generation_unavailable` alır. Çevrimdışı fikstürler öğrenci sonucu olarak gösterilmez.

## 4. Reddedilen yaklaşımlar

- Her soruda modelleme veya doğrulama için ikinci bir LLM çağrısı, AI hakem ve her öncül için ayrı LLM.
- Genel birim önekleri, sembolik fizik yasası seçimi ve tepkimenin gerçekleşme tahmini.
- Evrensel sahne grafiği ve grafik pikselinden değer okuma.
- Organel işlevi gibi alan bilgisini öğretmen incelemesi olmadan kod tablosuna yazmak (TA-007/TA-011).
- v2'yi kalıcı saklamak veya mevcut kayıtları taşımak.
