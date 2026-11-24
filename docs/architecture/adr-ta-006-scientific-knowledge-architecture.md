# ADR TA-006/TA-007 hazırlığı: Bilimsel bilgi mimarisi

Durum: önerildi (tasarım). TA-005C'de bu kayıt için kod, şema, kayıt defteri veya veri yoktur. Uygulama TA-006 (müfredat ve yöntem zekâsı) ve TA-007'de (uzman öğretmen bilgisi) yapılır. FKB (fizik, kimya, biyoloji) öğrenci üretimi kapalı kalır.

## Bağlam

TeacherAI bir soru çözücü değil; bilimsel olarak güvenilir, çok disiplinli ve kişiselleştirilmiş bir öğretmen olmayı hedefler. Bugün doğruluk büyük ölçüde iki şeye dayanır:

- Matematikte belirlenimci Python (MathAI, AnswerTarget)
- Diğer her şeyde dil modelinin çıktısı ve sunucu doğrulayıcılarının sınırları

Fizik, kimya ve biyoloji için yalnız çevrimdışı ve sınırlı denetimler vardır (`features/reasoning/`, TA-004).

Yalnız modele dayanmak bilimsel iddiaları kaynaksız bırakır. Yalnız ders kitabına dayanmak öğrenciye uyarlanamaz. Yalnız Python'a dayanmak biyolojinin kavramsal büyük bölümünü kapsayamaz. Karar dengeli, karma bir mimaridir.

## Karar 1: Beş tamamlayıcı temel

| # | Temel | Ne sağlar | Ne sağlamaz |
| --- | --- | --- | --- |
| 1 | Resmî müfredat ve eğitim bağlamı (MEB programları, Türkiye Yüzyılı Maarif Modeli, sınıf, sınav hedefi) | Kazanımın, düzeyin ve yöntemin **uygunluğu** | Bilimsel doğruluk |
| 2 | Yetkili bilimsel bilgi (kavramlar, yasalar, koşullar, istisnalar, sabitler) | İddianın kaynağa **dayanması** | Öğretim yöntemi, öğrenciye uygunluk |
| 3 | Bağımsız belirlenimci Python doğrulaması | Hesap, birim, korunum, denkleştirme, sembolik eşdeğerlik **kanıtı** | Yasa seçiminin doğruluğu, görselin doğru okunması |
| 4 | Çok kipli AI akıl yürütmesi | Dil, görsel anlama, bağlamsal açıklama, uyarlama | Doğrulama, onay veya müfredat kararı (sağlayıcı çıktısı bunları belirleyemez) |
| 5 | Gerçek öğretmen uzmanlığı | Yöntem, yaygın kavram yanılgısı, açıklama kalitesi, onay | Yerleşik bilimsel gerçeği değiştirme yetkisi |

Beş doğruluk boyutu (CLAUDE.md) bu temellerle eşlenir:

- Doğru soru: TA-003 ve 4
- Doğru cevap: 2 ve 3
- Uygun yöntem: 1 ve 5
- Tutarlı sunum: 3 ve 4
- Gerçek öğrenme: TA-012/013

Bir temel diğerinin kanıtı sayılmaz.

## Karar 2: Denge branşa göre değişir

Sabit çalışma zamanı yüzdeleri uygulanmaz. Daha önce konuşulan "altın oran" bir **tasarım ilkesidir**; bilimsel olarak kanıtlanmış bir sayısal optimum değildir ve kodda veya ayarda yer almaz.

| Branş | Ağırlık merkezi | Python'un rolü | Bilgi tabanının rolü |
| --- | --- | --- | --- |
| Matematik | Belirlenimci sembolik/sayısal doğrulama | Birincil kanıt (MathAI, ifade ayrıştırıcısı, hedef) | Tanım, teorem koşulu, yöntem uygunluğu |
| Fizik | Yasa + uygulanabilirlik koşulu + diyagram + birim + nicel hesap | Birim/boyut, formül, sayısal hesap, grafik okuma | Yasanın hangi koşulda geçerli olduğu (sürtünmesiz, sabit ivme, ideal gaz…) |
| Kimya | Kavram + kimyasal gösterim + tepkime + korunum + deney koşulu | Atom/yük korunumu, denkleştirme, stokiyometri | Tepkimenin gerçekleşip gerçekleşmediği, koşul, güvenlik. Dengeli denklem tepkimenin gerçekleştiğini **kanıtlamaz**. |
| Biyoloji | Yetkili kavram + yapı-işlev + süreç + deney | Dar ve sınırlı (DNA→mRNA, sıra/etiket, oran) | Birincil kaynak. Doğrulayıcısı olmayan iddia `not_checked` kalır. |

## Karar 3: Akademik kaynak kütüphanesi (yalnız aday liste)

Aşağıdakiler **sonradan değerlendirilecek adaylardır**. TA-005C'de hiçbiri edinilmedi, okunmadı, alıntılanmadı veya içeri alınmadı.

| Alan | Adaylar |
| --- | --- |
| Matematik | Michael Sullivan, *Algebra and Trigonometry*; James Stewart, *Calculus*; George Pólya, *How to Solve It*; uygun geometri, olasılık ve istatistik kaynakları (seçilmedi) |
| Fizik | Serway ve Jewett, *Physics for Scientists and Engineers*; BIPM SI başvuruları; NIST fiziksel sabitleri; uygun resmî bilimsel veri kaynakları |
| Kimya | Brown ve LeMay, *Chemistry: The Central Science*; Raymond Chang, *Chemistry*; IUPAC terminolojisi; PubChem ve diğer yetkili kimya veritabanları |
| Biyoloji | *Campbell Biology*; uygun hücre ve moleküler biyoloji kaynakları; NCBI Bookshelf ve yetkili biyoloji kaynakları |
| Eğitim kapsamı | MEB öğretim programları; Türkiye Yüzyılı Maarif Modeli; MEB ders kitapları ve eğitim kaynakları; OGM Materyal; ÖSYM soru tipi analizi |

Hukuki ve teknik ayrım dört ayrı kategoridir. Biri diğerinin izni sayılmaz:

1. **Akademik başvuru:** bir uzmanın kaynağı okuyup kendi sözleriyle özgün bilgi yazması.
2. **Lisanslı içeri alma:** metnin veya verinin sisteme alınması; açık lisans veya sözleşme gerekir.
3. **Yeniden dağıtım:** içeriğin öğrenciye aynen veya türetilmiş olarak gösterilmesi.
4. **Model eğitimi:** içerikle model eğitmek veya ince ayar yapmak.

Bir ders kitabını satın almak onu ticari bir AI bilgi tabanında çoğaltma hakkı vermez. Kesin lisansı doğrulanmadan hiçbir kaynak "ticari olarak yeniden kullanılabilir" gösterilmez. Kamu kurumu yayınları (MEB, ÖSYM) da kendi kullanım koşullarıyla ayrıca değerlendirilir. Bir kaynağın kamuya açık olması lisans anlamına gelmez.

Her kaynak kaydı ileride şunları taşır:

- baskı veya sürüm
- köken (nereden, kim, ne zaman edindi)
- lisans ve izin verilen kullanım (yukarıdaki dört kategoriden hangileri)
- inceleme durumu

## Karar 4: Bilgi veri kümesi sınırları (TA-006/TA-007)

Ayrı tutulacak veri türleri:

1. Müfredat kazanımları ve program sürümleri (MEB 2018 ve Maarif Modeli ayrı sürüm)
2. Bilimsel gerçekler, yasalar ve kavramlar
3. Formül uygulanabilirliği ve sınırları
4. Öğretim yöntemleri
5. Öğretmen onaylı açıklamalar
6. Yaygın kavram yanılgıları
7. Görsel ve deneysel bilgi
8. Özgün çözümlü sorular
9. Bağımsız değerlendirme veri kümeleri (eğitim/üretim verisiyle karışmaz; cevap anahtarı modelden türetilmez)

Her bilimsel bilgi girdisi ileride şu alanları taşır:

| Alan | Not |
| --- | --- |
| Kararlı kimlik | Sürümler arasında değişmez |
| Branş, konu, alt konu | Kanonik alan kimlikleri (TA-002) |
| Eğitim düzeyi | Sınıf ve/veya sınav hedefi; ayrı eksenler |
| Ön koşul ilişkileri | Yönlü bağ |
| Bilimsel ifade | Özgün yazım; kaynaktan aynen kopya değil |
| Geçerlilik koşulları | Ör. "yalnız sabit ivmede" |
| Bilinen istisnalar | Ör. ideal gaz sapması |
| Kaynak ve köken | Karar 3'teki kayıtlara bağlı |
| İnceleme ve onay durumu | `draft` / `reviewed` / `approved`; kim, ne zaman, hangi kanıtla |
| İlişkili doğrulama yeteneği | Hangi Python denetleyicisi var; yoksa `not_checked` |

Değişmez ilkeler:

- **Müfredat uygunluğu ile bilimsel doğruluk ayrı boyutlardır.** Bir ifade doğru ama düzeye uygunsuz, ya da müfredatta geçen ama sadeleştirilmiş olabilir. İkisi ayrı alanlarda tutulur.
- **Öğretmen tercihi yerleşik bilimsel gerçeği geçersiz kılamaz.** Öğretmen yöntemi, sırayı ve açıklamayı belirler. Bilimsel ifadeyi değiştirmek bilimsel inceleme ister.
- **AI tarafından yazılmış eğitim bilgisi otomatik onaylanmaz.** Taslak olarak girer. Onay yalnız kayıtlı bir öğretmen veya alan uzmanı değerlendirmesiyle verilir. Sağlayıcı çıktısı onay belirleyemez.
- **Büyük boş kayıt defterleri açılmaz ve erken vektör veritabanı kurulmaz.** Kayıt, gerçekten kullanılan ilk kazanım ve kavramlarla başlar (TA-005'teki 8. sınıf matematik kaydı gibi). Geri getirme (retrieval) ihtiyacı ölçüldüğünde, küçük ve kaynaklı bir kümede değerlendirilir.

## Karar 5: Çalışma zamanı verimliliği ve öğretim kalitesi

1. Python güvenilir biçimde doğrulayabildiği hesabı yapar.
2. AI dil, görsel anlama ve bağlamsal akıl yürütme için kullanılır.
3. Bilimsel iddialar seçilmiş bilgiye dayanır.
4. Öğretim yöntemi öğretmen uzmanlığıyla gelişir.
5. İlgisiz akademik içerik geri getirilmez. Bağlam bütçesi (`lesson_context_max_bytes`) korunur.
6. Tek çağrı yetiyorsa çok çağrı yapılmaz (mantıksal istek tavanı). Bilgi araması ek ücretli çağrı gerektirmemelidir.
7. Gereksiz öğrenci netleştirmesi yapılmaz (TA-003 önemlilik kuralı).
8. Gerçek yetenekten fazla bilimsel doğrulama iddia edilmez. Denetleyicisi olmayan iddia `unsupported`/`not_checked` kalır.

Fizik, kimya ve biyoloji mimaride birinci sınıf branştır. Bu, öğrenci üretimi açılmış demek değildir. Bitmemiş FKB öğrenci üretim yolları bu fazda **açılmadı**: üretim isteği 422 `subject_generation_unavailable` döner (TA-002).

Akademik kaynak mimarisi TA-006'yı geciktirmek için bir gerekçe değildir. TA-006 önce müfredat kaydını, yöntem politikalarını ve öğretmen değerlendirme kaydını gerçek kullanımla genişletir; kaynak kütüphanesi lisans değerlendirmesi ilerledikçe eklenir.

## TA-006 için başlangıç noktası

- `features/education/curriculum.py` `CurriculumRegistry` (ADR TA-005B §TA-006 bağlantısı): branş, sınav hedefi, program sürümü, alt kazanım, ön koşul, yöntem geçerlilik koşulu, öğretmen değerlendirme kaydı, onay durumu, kanıt düzeyi.
- `features/reasoning/`: denetleyici kapsamı her bilgi girdisinin "ilişkili doğrulama yeteneği" alanına bağlanır.
- Değerlendirme: `python -m scripts.evaluate_models readiness` dört branşın dengesini ve eksik görsel/anahtar durumunu gösterir. Gerçek kalite ölçümü öğretmen anahtarı ve onaylı bütçe ister.

## Reddedilenler

- Yalnız modele dayanan bilimsel içerik
- Ders kitaplarının toplu içeri alınması (lisans yok)
- Sabit yüzdelik "altın oran" kuralı
- Bu fazda boş kayıt defterleri veya vektör veritabanı
- AI taslaklarının otomatik onayı
