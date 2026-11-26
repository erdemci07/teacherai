# TA-008 bilimsel bilgi kapsam raporu

Bu dosya `python -m scripts.knowledge_registry` ile üretilir; elle düzenlenmez.

- Kayıt sürümü: `1.0.0+61fba2b6e2c2`
- Kaynak: 42 · bilgi girdisi: 346 · tanımlı denetleyici: 47

Bütün girdiler `claude-draft` taslağıdır. Hiçbiri öğretmen veya alan uzmanınca incelenmedi; inceleyen yetki kaydı
boştur (0 yetkili). Bu yüzden çalışma zamanına uygun girdi sayısı 0'dır. Denetleyici
bağlantısı iddianın yalnız belirtilen parçasını kapsar.

| Alan | Girdi | Kaynaklı | Kaynaksız | Kazanıma bağlı | Denetleyicili | İncelenen | Çalışma zamanına uygun | Tür dağılımı |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Matematik (geometri dahil) | 175 | 174 | 1 | 40 | 73 | 0 | 0 | definition 49, fact 5, method 38, relationship 44, theorem 39 |
| Fizik | 65 | 65 | 0 | 21 | 43 | 0 | 0 | definition 15, fact 4, law 17, method 4, relationship 23, theorem 2 |
| Kimya | 45 | 45 | 0 | 16 | 14 | 0 | 0 | definition 13, fact 1, law 5, relationship 26 |
| Biyoloji | 45 | 45 | 0 | 24 | 9 | 0 | 0 | definition 5, fact 3, law 2, process 23, relationship 12 |
| Ortaokul fen (bütünleşik) | 16 | 16 | 0 | 7 | 1 | 0 | 0 | fact 1, process 2, relationship 13 |

| Alan | Düzeltilen (sürüm 2+) | Müfredat başlığına bağlı | Kaynak kullanım sınıfı |
| --- | --- | --- | --- |
| Matematik (geometri dahil) | 2 | 4 | independent_fact 174, unresolved 1 |
| Fizik | 41 | 24 | independent_fact 65 |
| Kimya | 1 | 22 | independent_fact 45 |
| Biyoloji | 6 | 9 | independent_fact 45 |
| Ortaokul fen (bütünleşik) | 2 | 9 | independent_fact 16 |

## TA-007 bağımsız taslak denetimi

`apps/api/app/features/knowledge/audit/TA-007-draft-audit.json`: 74 TA-006 taslağı. Eylem: needs_expert 2, no_change 59, revised 13. Bulgu düzeyi: info 60, major 8, minor 6.
AI destekli denetimdir; uzman onayı değildir. Düzeltilen girdiler önceki sürümü `revisions` içinde korur.
Uzman kararı gereken girdiler: `chem.atom-ion-molecule`, `chem.equilibrium-constant`.

## TA-006 → TA-007

| Ölçü | TA-006 | TA-007 |
| --- | --- | --- |
| Kaynak | 30 | 42 |
| Bilgi girdisi | 74 | 346 |
| Matematik (geometri dahil) | 19 | 175 |
| Fizik | 18 | 65 |
| Kimya | 16 | 45 |
| Biyoloji | 15 | 45 |
| Ortaokul fen (bütünleşik) | 6 | 16 |
| Çalışma zamanına uygun | 0 | 0 |

## Matematik ve geometri kapsamı (TA-008)

175 girdi (geometri 30); denetleyici bağlantılı 73; hepsi `draft`, hak kararı `pending`. Denetleyici bağlantısı iddianın yalnız belirtilen parçasını kapsar.

| Konu | Girdi |
| --- | --- |
| `aci_kavrami` | 3 |
| `analitik_geometri` | 6 |
| `carpanlar_ve_katlar` | 3 |
| `cebirsel_ifadeler` | 4 |
| `cember_daire` | 4 |
| `denklem_sistemleri` | 4 |
| `diziler` | 3 |
| `dogrusal_denklemler` | 3 |
| `dortgen_cokgen` | 3 |
| `esitsizlikler` | 3 |
| `eslik_benzerlik` | 3 |
| `fonksiyon_donusumleri` | 1 |
| `fonksiyonlar` | 12 |
| `ikinci_dereceden_denklemler` | 6 |
| `ikinci_dereceden_fonksiyonlar` | 2 |
| `integral` | 5 |
| `islem_onceligi` | 1 |
| `istatistik` | 5 |
| `karekoklu_ifadeler` | 7 |
| `kati_cisimler` | 2 |
| `kesirler` | 6 |
| `koklu_denklemler` | 3 |
| `kosullu_olasilik` | 3 |
| `kumeler` | 2 |
| `limit` | 4 |
| `logaritma` | 3 |
| `mutlak_deger` | 3 |
| `olasilik` | 5 |
| `oran_oranti` | 2 |
| `ozdeslikler` | 2 |
| `parcali_fonksiyonlar` | 1 |
| `polinomlar` | 1 |
| `problem_cozme` | 2 |
| `rasyonel_denklemler` | 3 |
| `sayilar` | 4 |
| `sayma` | 5 |
| `sozel_problemler` | 6 |
| `sureklilik` | 1 |
| `tam_sayilar` | 2 |
| `trigonometri` | 12 |
| `turev` | 8 |
| `ucgenler` | 9 |
| `uslu_ifadeler` | 3 |
| `ustel_fonksiyonlar` | 1 |
| `yuzdeler` | 4 |

| Kaynak | Girdi başvurusu |
| --- | --- |
| `joyce.euclid-elements` | 8 |
| `openstax.algebra-and-trigonometry-2e` | 12 |
| `openstax.calculus-volume-1` | 19 |
| `openstax.college-algebra-2e` | 31 |
| `openstax.contemporary-mathematics` | 13 |
| `openstax.elementary-algebra-2e` | 34 |
| `openstax.intermediate-algebra-2e` | 12 |
| `openstax.introductory-statistics-2e` | 11 |
| `openstax.prealgebra-2e` | 38 |

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
| `halliday-resnick-walker.fundamentals` | textbook | not_accessed | — | hayır | evet | hayır | hayır | hayır | 0 |
| `iupac.gold-book` | reference_work | access_restricted | — | hayır | bilinmiyor | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `joyce.euclid-elements` | classic | open_web | — | hayır | evet | hayır | hayır | hayır | 8 |
| `libretexts` | oer_platform | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `meb.ogretim-programlari` | official_curriculum | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `mit.ocw` | oer_platform | open_web | CC BY-NC-SA 4.0 | evet | evet | hayır | koşullu | hayır | 0 |
| `nasa.planetary-fact-sheet` | reference_data | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 1 |
| `nih.ncbi-bookshelf` | oer_platform | access_restricted | — | hayır | bilinmiyor | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `nih.pubchem` | database | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `nist.codata` | reference_data | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 1 |
| `nist.sp-811` | standard | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `openstax.algebra-and-trigonometry-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 12 |
| `openstax.astronomy-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 1 |
| `openstax.biology-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 52 |
| `openstax.calculus-volume-1` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 19 |
| `openstax.chemistry-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 49 |
| `openstax.college-algebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 31 |
| `openstax.college-physics-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | hayır | koşullu | hayır | 1 |
| `openstax.contemporary-mathematics` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 13 |
| `openstax.elementary-algebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 34 |
| `openstax.intermediate-algebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 12 |
| `openstax.introductory-statistics-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 11 |
| `openstax.prealgebra-2e` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | koşullu | koşullu | bilinmiyor | 38 |
| `openstax.university-physics-volume-1` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | hayır | koşullu | hayır | 47 |
| `openstax.university-physics-volume-2` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | hayır | koşullu | hayır | 16 |
| `openstax.university-physics-volume-3` | open_textbook | open_web | CC BY-NC-SA 4.0 | evet | evet | hayır | koşullu | hayır | 6 |
| `polya.how-to-solve-it` | classic | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `serway-jewett-peroomian.physics-11e` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `serway-jewett.physics` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `serway-jewett.physics-modern-10e` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `siyavula.mathematics-10` | open_textbook | open_web | — | hayır | evet | bilinmiyor | bilinmiyor | bilinmiyor | 0 |
| `siyavula.physical-sciences-10` | open_textbook | open_web | CC BY (sürüm sayfada belirtilmedi) | evet | evet | koşullu | koşullu | bilinmiyor | 0 |
| `stewart.calculus` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `sullivan.algebra-trigonometry` | textbook | purchase_required | — | hayır | evet | hayır | hayır | hayır | 0 |
| `young-freedman.university-physics` | textbook | not_accessed | — | hayır | evet | hayır | hayır | hayır | 0 |

## Denetleyici kapsamı

| Denetleyici | Kanıtlar | Kanıtlamaz | Bağlı girdi |
| --- | --- | --- | --- |
| `integrity.expression_ast` | Kök, kesir ve üs kapsamı; tekli eksinin yeri; ifadenin dengeli yapısı. | Matematiksel doğruluğu; yalnız yapıyı ayrıştırır. | 4 |
| `mathai.answer_target` | Sorunun istediği hedefin (x, x+2, kök toplamı…) belirlenimci tespiti. | Hedefin sorunun bağlamına uygun yorumlandığını (önce bütünlük denetimi gerekir). | 0 |
| `mathai.constant_expression` | Değişkensiz kök, üs ve kesir ifadesinin kesin gerçel değeri. | İfadenin sorudaki niceliği doğru temsil ettiğini. | 12 |
| `mathai.equation_roots` | Aday köklerin özgün tek değişkenli gerçel denklemi sağlaması, yabancı ve kayıp kök. | Görselin doğru okunduğunu, sözel gerekçeyi veya yöntemin uygunluğunu. | 6 |
| `mathai.inequality_solution` | Tek değişkenli eşitsizlikte adım sonrası çözüm kümesi ve yön değişimi. | Çok değişkenli eşitsizlikleri ve grafik yorumunu. | 1 |
| `mathematics.antiderivative` | Önerilen ters türevin türevinin integrand olduğu. | Belirli integralin alanla aynı olduğunu. | 2 |
| `mathematics.calculus_extremum` | Kritik noktalar ve birinci türev testiyle yerel ekstremum (türev sıfır ama ekstremum yok durumu dahil). | Mutlak ekstremum için aralık uçlarının ayrıca incelenmesi gerektiğini. | 3 |
| `mathematics.definite_integral` | İşaretli belirli integral, geometrik alan ve genelleştirilmiş integral ayrımı. | Kapalı biçim bulunamayan integrali. | 2 |
| `mathematics.function_domain` | Fonksiyonun gerçel tanım kümesi, tanımsız noktaları ve grafiğin kopuk parçaları. | Grafiğin görselden doğru okunduğunu; örnek noktalar kanıt değildir. | 5 |
| `mathematics.geometry_constraints` | Kullanılabilir olgulardan kısıt sistemi: hedefin belirli, belirsiz, çok değerli veya tutarsız olduğu. | Görünüşe dayanan olguları; yardımcı çizimin tanımından izlemeyen olguları. | 4 |
| `mathematics.inequality_set` | Tek değişkenli eşitsizliğin açık/kapalı uçlu, kopuk aralıklı kesin çözüm kümesi. | Parametreye bağlı işaret durumlarını. | 4 |
| `mathematics.inverse_function` | Tanım kümesinde birebirlik ve tek gerçel ters dal. | Kısıtlanmış tanım kümesinin soruda verildiğini. | 1 |
| `mathematics.probability_exact` | Yerine koyarak/koymadan çekilişte kesin olasılık, koşullu olasılık ve bağımsızlık. | Çıktıların eşit olasılıklı olduğu varsayımının soruya uygun olduğunu. | 7 |
| `mathematics.similarity_correspondence` | Benzerlik/eşlikte köşe eşlemesinin verilen uzunluklarla tutarlılığı. | Benzerlik ölçütünün soruda gerçekten sağlandığını. | 3 |
| `mathematics.solution_set` | Seçilen sayı kümesinde, özgün tanım kümesi uygulanmış kesin çözüm kümesi (sonsuz, boş, sonlu). | Denklemin sorudan doğru kurulduğunu; koşullu veya parametreli sonucu doğrulanmış saymaz. | 8 |
| `mathematics.statistics` | Ortalama, ortanca, tepe değer, açıklık ve varyansın kesin hesabı. | Verinin tablo veya grafikten doğru okunduğunu. | 2 |
| `mathematics.transformation` | Ardışık iki adımın özgün tanım kümesinde denk, genişleten veya kaybettiren olduğu. | Adımın öğrenciye uygun açıklandığını. | 4 |
| `mathematics.triangle_inequality` | Kenar uzunluklarının üçgen eşitsizliğini sağladığı (dejenere/imkânsız üçgen). | Açıların veya şeklin ölçekli olduğunu. | 2 |
| `mathematics.trig_interval` | Derece/radyan ayrımıyla verilen aralıktaki bütün kökler (periyodik çözümler kaybolmadan). | Aralık verilmediğinde sonlu bir hedef belirlemez. | 2 |
| `mathematics.word_problem_model` | Sözel problem modelinin tutarlılığı, hedefin tek değerli olduğu ve bilinen değerlerin metinde geçtiği. | İlişkilerin soru metnine uygun kurulduğunu (model sadakati kısmi denetlenir). | 6 |
| `physics.circuits.equivalent_resistance` | İki düğüm arasındaki eşdeğer direnç (test kaynağıyla). | Elemanların ohmik olduğunu (görünür varsayım). | 1 |
| `physics.circuits.nodal` | Bağlantı grafiğinden düğüm gerilimleri, eleman akımları ve Kirchhoff akım dengesi. | Görselden okunan bağlantının doğru olduğunu; belirsiz bağlantı çözülmez. | 5 |
| `physics.conventions.values` | Soru uzlaşımları (g, sin/cos, π) ve yazılı idealleştirmeler. | Metnin görselden doğru okunduğunu. | 2 |
| `physics.dynamics.newton` | Tek cisim ve iple bağlı iki cisimde ivme, gerilme, tepki; statik–kinetik karar. | Kuvvetlerin soruda gerçekten kurulduğunu (kaynak denetimi ayrıdır). | 7 |
| `physics.energy.conservation` | Tek cisim tek evrede enerji korunumu; sürtünme işi hesaba katılarak. | Korunumsuz kuvvetin olmadığını; bu koşul ayrıca değerlendirilir. | 5 |
| `physics.graphs.velocity_time` | Basılı hız–zaman noktalarından işaretli alan, |v| alanı ve eğim sabitliği. | Piksellerden okunan değerleri; yalnız basılı değerler kullanılır. | 3 |
| `physics.kinematics.constant_acceleration` | Sabit ivmeli hareketin beş bağıntısından yalnız hedef; evre zinciri; alınan yol. | İvmenin gerçekten sabit olduğunu (koşul ayrıca denetlenir) veya görselin doğru okunduğunu. | 3 |
| `physics.laws.applicability` | Yasanın koşullarını satisfied/violated/unknown olarak değerlendirir. | Bilinmeyen koşulun sağlandığını; varsayım yalnız görünür yazılır. | 7 |
| `physics.momentum.collision` | Tek doğrultuda esnek, tamamen esnek olmayan çarpışma ve bilinmeyen tek hız. | Net dış itmenin sıfır olduğunu; sistem sınırı kaynakta kurulmalıdır. | 2 |
| `reasoning.chemistry.balance` | Atom ve yük dengesi, en küçük tam sayı katsayılar. | Tepkimenin gerçekleştiğini, kendiliğindenliği, hızı veya koşulları. | 5 |
| `reasoning.chemistry.limiting_reactant` | Sınırlayıcı bileşen ve kuramsal ürün miktarı. | Gerçek verimi. | 1 |
| `reasoning.chemistry.parse_species` | Formülün bileşimi, hâli ve yükü (yazım düzeyinde). | Türün gerçekte var olduğunu veya kararlılığını. | 1 |
| `reasoning.chemistry.redox_electrons` | Yükseltgenme basamağı değişiminden aktarılan elektron sayısı. | Tepkimenin istemli olduğunu. | 2 |
| `reasoning.chemistry.stoichiometry` | Denkleşmiş denklemden mol oranıyla miktar. | Verimi ve tepkimenin tam yürüdüğü varsayımının geçerliliğini. | 2 |
| `reasoning.evidence.claim` | Verilen deney verisinin iddiayı destekleyip desteklemediği. | Verinin kaynağını; genellemenin bütün koşullarda geçerli olduğunu. | 2 |
| `reasoning.evidence.constant_ratio` | Tablodaki iki değişkenin oranının sabitliği. | İlişkinin nedensel olduğunu veya yasanın geçerlilik koşullarını. | 3 |
| `reasoning.evidence.controlled_comparison` | Deney gruplarında yalnız bir değişkenin değiştiği. | Deneyin gerçekten yapıldığını veya ölçümlerin doğruluğunu. | 3 |
| `reasoning.evidence.sequence_order` | Verilen süreç sırasının modeldeki sırayla uyumu. | Modelin biyolojik olarak doğru olduğunu (model kaynaktan gelmelidir). | 1 |
| `reasoning.formula.dimensions` | Formül iki tarafının boyut eşitliği. | Formülün fiziksel olarak doğru olduğunu. | 5 |
| `reasoning.formula.evaluate` | Verilen formülde birimli yerine koyma ve sayısal sonuç. | Formülün bu duruma uygulanabilir olduğunu (koşullar ayrıca denetlenmez). | 18 |
| `reasoning.formula.graph_area` | Parçalı doğrusal grafiğin altındaki alan. | Alanın fiziksel yorumunun soruya uygunluğunu. | 2 |
| `reasoning.formula.graph_slope` | Grafikte iki nokta arası eğim ve birimi. | Grafiğin görselden doğru okunduğunu. | 3 |
| `reasoning.quantities.compare` | Kimlik, tür, boyut, birim, işaret ve yaklaşım politikasıyla cevap karşılaştırması. | İstenen hedefin doğru belirlendiğini (hedef ayrıca kurulur). | 6 |
| `reasoning.sequence.codon` | mRNA'da belirli konumdaki kodon. | Okuma çerçevesinin biyolojik olarak doğru seçildiğini. | 1 |
| `reasoning.sequence.transcription` | Kalıp DNA'dan tamamlayıcı mRNA dizisi. | Gen ifadesinin düzenlenmesini veya biyolojik işlevi. | 2 |
| `reasoning.units.conversion` | Önekli ve türetilmiş birimler arasında kesin dönüşüm. | Ölçümün doğruluğunu veya anlamlı basamakları. | 4 |
| `reasoning.units.dimension` | İki niceliğin veya bir formülün boyut uyumu. | Doğru fizik yasasının seçildiğini; boyutça doğru formül yanlış yasa olabilir. | 5 |

Girdi düzeyinde iddia durumu: `partially_checked` 140, `not_checked` 206, `passed` 0 (yapı gereği).
