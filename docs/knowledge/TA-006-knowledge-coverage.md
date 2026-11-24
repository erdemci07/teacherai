# TA-006 bilimsel bilgi kapsam raporu

Bu dosya `python -m scripts.knowledge_registry` ile üretilir; elle düzenlenmez.

- Kayıt sürümü: `1.0.0+0e32f7341e8a`
- Kaynak: 30 · bilgi girdisi: 74 · tanımlı denetleyici: 22

Bütün girdiler `claude-draft` taslağıdır. Hiçbiri öğretmen veya alan uzmanınca incelenmedi; bu yüzden çalışma
zamanına uygun girdi sayısı 0'dır. Denetleyici bağlantısı iddianın yalnız belirtilen parçasını kapsar.

| Alan | Girdi | Kaynaklı | Kaynaksız | Kazanıma bağlı | Denetleyicili | İncelenen | Çalışma zamanına uygun | Tür dağılımı |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Matematik (geometri dahil) | 19 | 18 | 1 | 18 | 11 | 0 | 0 | definition 5, fact 1, method 1, relationship 2, theorem 10 |
| Fizik | 18 | 18 | 0 | 13 | 13 | 0 | 0 | definition 3, fact 2, law 6, method 1, relationship 5, theorem 1 |
| Kimya | 16 | 16 | 0 | 10 | 12 | 0 | 0 | definition 5, fact 1, law 4, relationship 6 |
| Biyoloji | 15 | 15 | 0 | 15 | 9 | 0 | 0 | definition 1, fact 2, law 1, process 7, relationship 4 |
| Ortaokul fen (bütünleşik) | 6 | 6 | 0 | 6 | 1 | 0 | 0 | relationship 6 |

Kaynaksız girdiler (çalışma zamanına kapalı): `math.polya-problem-solving`

## Kaynaklar ve izinler

Dört izin ayrıdır: akademik başvuru, içeri alma/dönüştürme, öğrenciye yeniden dağıtım, model eğitimi.

| Kaynak | Tür | Erişim | Lisans | Lisans doğrulandı | Başvuru | İçeri alma | Dağıtım | Eğitim | Kullanan girdi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `active-calculus` | open_textbook | open_web | CC BY-SA (sürüm doğrulanmadı) | evet | evet | koşullu | koşullu | bilinmiyor | 0 |
| `aim.open-textbook-initiative` | oer_platform | not_accessed | — | hayır | bilinmiyor | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `bccampus.concepts-of-biology-1ce` | open_textbook | open_web | CC BY 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 0 |
| `bipm.si-brochure-9` | standard | open_web | CC BY 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 2 |
| `brown-lemay.central-science` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `campbell.biology` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `chang.chemistry` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `iupac.gold-book` | reference_work | access_restricted | — | hayır | bilinmiyor | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `libretexts` | oer_platform | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `meb.ogretim-programlari` | official_curriculum | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `nasa.planetary-fact-sheet` | reference_data | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 1 |
| `nih.ncbi-bookshelf` | oer_platform | access_restricted | — | hayır | bilinmiyor | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `nih.pubchem` | database | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `nist.codata` | reference_data | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 1 |
| `openstax.biology-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 19 |
| `openstax.calculus-volume-1` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 2 |
| `openstax.chemistry-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 19 |
| `openstax.college-algebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 3 |
| `openstax.elementary-algebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 3 |
| `openstax.intermediate-algebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 5 |
| `openstax.introductory-statistics-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 2 |
| `openstax.prealgebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 4 |
| `openstax.university-physics-volume-1` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 15 |
| `openstax.university-physics-volume-2` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 3 |
| `polya.how-to-solve-it` | classic | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `serway-jewett.physics` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `siyavula.mathematics-10` | open_textbook | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `siyavula.physical-sciences-10` | open_textbook | open_web | CC BY (sürüm sayfada belirtilmedi) | evet | evet | koşullu | koşullu | bilinmiyor | 0 |
| `stewart.calculus` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `sullivan.algebra-trigonometry` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |

## Denetleyici kapsamı

| Denetleyici | Kanıtlar | Kanıtlamaz | Bağlı girdi |
| --- | --- | --- | --- |
| `integrity.expression_ast` | Kök, kesir ve üs kapsamı; tekli eksinin yeri; ifadenin dengeli yapısı. | Matematiksel doğruluğu; yalnız yapıyı ayrıştırır. | 2 |
| `mathai.answer_target` | Sorunun istediği hedefin (x, x+2, kök toplamı…) belirlenimci tespiti. | Hedefin sorunun bağlamına uygun yorumlandığını (önce bütünlük denetimi gerekir). | 0 |
| `mathai.constant_expression` | Değişkensiz kök, üs ve kesir ifadesinin kesin gerçel değeri. | İfadenin sorudaki niceliği doğru temsil ettiğini. | 6 |
| `mathai.equation_roots` | Aday köklerin özgün tek değişkenli gerçel denklemi sağlaması, yabancı ve kayıp kök. | Görselin doğru okunduğunu, sözel gerekçeyi veya yöntemin uygunluğunu. | 4 |
| `mathai.inequality_solution` | Tek değişkenli eşitsizlikte adım sonrası çözüm kümesi ve yön değişimi. | Çok değişkenli eşitsizlikleri ve grafik yorumunu. | 1 |
| `reasoning.chemistry.balance` | Atom ve yük dengesi, en küçük tam sayı katsayılar. | Tepkimenin gerçekleştiğini, kendiliğindenliği, hızı veya koşulları. | 5 |
| `reasoning.chemistry.limiting_reactant` | Sınırlayıcı bileşen ve kuramsal ürün miktarı. | Gerçek verimi. | 1 |
| `reasoning.chemistry.parse_species` | Formülün bileşimi, hâli ve yükü (yazım düzeyinde). | Türün gerçekte var olduğunu veya kararlılığını. | 1 |
| `reasoning.chemistry.redox_electrons` | Yükseltgenme basamağı değişiminden aktarılan elektron sayısı. | Tepkimenin istemli olduğunu. | 1 |
| `reasoning.chemistry.stoichiometry` | Denkleşmiş denklemden mol oranıyla miktar. | Verimi ve tepkimenin tam yürüdüğü varsayımının geçerliliğini. | 2 |
| `reasoning.evidence.claim` | Verilen deney verisinin iddiayı destekleyip desteklemediği. | Verinin kaynağını; genellemenin bütün koşullarda geçerli olduğunu. | 2 |
| `reasoning.evidence.constant_ratio` | Tablodaki iki değişkenin oranının sabitliği. | İlişkinin nedensel olduğunu veya yasanın geçerlilik koşullarını. | 2 |
| `reasoning.evidence.controlled_comparison` | Deney gruplarında yalnız bir değişkenin değiştiği. | Deneyin gerçekten yapıldığını veya ölçümlerin doğruluğunu. | 3 |
| `reasoning.evidence.sequence_order` | Verilen süreç sırasının modeldeki sırayla uyumu. | Modelin biyolojik olarak doğru olduğunu (model kaynaktan gelmelidir). | 1 |
| `reasoning.formula.dimensions` | Formül iki tarafının boyut eşitliği. | Formülün fiziksel olarak doğru olduğunu. | 2 |
| `reasoning.formula.evaluate` | Verilen formülde birimli yerine koyma ve sayısal sonuç. | Formülün bu duruma uygulanabilir olduğunu (koşullar ayrıca denetlenmez). | 12 |
| `reasoning.formula.graph_area` | Parçalı doğrusal grafiğin altındaki alan. | Alanın fiziksel yorumunun soruya uygunluğunu. | 1 |
| `reasoning.formula.graph_slope` | Grafikte iki nokta arası eğim ve birimi. | Grafiğin görselden doğru okunduğunu. | 2 |
| `reasoning.sequence.codon` | mRNA'da belirli konumdaki kodon. | Okuma çerçevesinin biyolojik olarak doğru seçildiğini. | 1 |
| `reasoning.sequence.transcription` | Kalıp DNA'dan tamamlayıcı mRNA dizisi. | Gen ifadesinin düzenlenmesini veya biyolojik işlevi. | 2 |
| `reasoning.units.conversion` | Önekli ve türetilmiş birimler arasında kesin dönüşüm. | Ölçümün doğruluğunu veya anlamlı basamakları. | 3 |
| `reasoning.units.dimension` | İki niceliğin veya bir formülün boyut uyumu. | Doğru fizik yasasının seçildiğini; boyutça doğru formül yanlış yasa olabilir. | 4 |

Girdi düzeyinde iddia durumu: `partially_checked` 46, `not_checked` 28, `passed` 0 (yapı gereği).
