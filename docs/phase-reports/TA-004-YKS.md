# TA-004 · YKS kaynak incelemesi

21 Kasım 2026 tarihinde proje sahibinin indeksindeki 20 soru resmî TYT ve AYT temel kitapçıklarından açıldı. Soru numaraları ve görsel ilişkiler 14 farklı PDF sayfasında kontrol edildi. Her branştan beş soru var. Aşağıdaki notlar mühendislik incelemesidir. Özgün 24 soruluk regresyon paketinin puanlaması ayrı kalır. Sınav soruları, şekiller ve cevap anahtarları depoya veya eğitim verisine aktarılmadı.

| Branş | Test ve soru | Basılı / PDF sayfası | Sistem için gözlem |
| --- | --- | --- | --- |
| Matematik | TYT 3 | 23 / [25](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_tyt_2026_kitapcik_d350.pdf#page=25) | Kapsamı farklı kök çizgileri ayrı okunmalı. Kök belirsizliği denetimi mevcut. |
| Matematik | TYT 12 | 26 / [28](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_tyt_2026_kitapcik_d350.pdf#page=28) | Aynı eksendeki üç renkli doğrunun kimliği verilen ilişkilerle bulunuyor. Basılmamış fonksiyon adları görselden atanamaz. |
| Matematik | AYT 33 | 34 / [36](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=36) | Sabit parçalar ve dönen parçanın ardışık konumları ayrılmalı. Özel dönme çözücüsü yok. |
| Matematik | AYT 34 | 34 / [36](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=36) | İstenen yay ile aynı uçlu kiriş ayrılmalı. Başka bir eşitlik eksik yay işaretini karşılamaz. |
| Matematik | AYT 40 | 36 / [38](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=38) | Ölçüler anlatı içinde, karşılaştırma koşulu soru kökünde. İkisi birlikte korunmalı. |
| Fizik | TYT 2 | 35 / [37](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_tyt_2026_kitapcik_d350.pdf#page=37) | Aynı başlangıç ve bitiş için rota uzunluğu ile yönlü yer değiştirme ayrılmalı. |
| Fizik | AYT 1 | 37 / [39](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=39) | Kuvvet oku hangi cisme bağlı? Zeminle temas varsayımı metinde açıkça aranmalı. |
| Fizik | AYT 3 | 37 / [39](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=39) | İki ayrı yol için ortak koşullar ve üç ayrı öncül var. Kesinlik bildiren sözcük korunmalı. |
| Fizik | AYT 7 | 39 / [41](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=41) | Seçeneklerin kendisi devre simgesi. Metin seçeneklerinden devre elemanı uydurulamaz. |
| Fizik | AYT 8 | 39 / [41](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=41) | Konum ve istenen kuvvet oranı ayrı okunmalı. Tek başına merkezcil ivme ara değerdir. |
| Kimya | TYT 8 | 37 / [39](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_tyt_2026_kitapcik_d350.pdf#page=39) | İki tanecik panelinde renk ve gruplanma farklı kanıtlar. Olumsuz soru kökü korunmalı. |
| Kimya | TYT 12 | 39 / [41](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_tyt_2026_kitapcik_d350.pdf#page=41) | Birden fazla başlangıç karışımında sınırlayıcı madde ayrı belirlenmeli. Mol oranı denetleyicisi mevcut. |
| Kimya | AYT 20 | 42 / [44](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=44) | Basamak engeli yerel minimuma göre ölçülür. En yüksek tepe tek başına en büyük engeli belirlemez. |
| Kimya | AYT 23 | 42 / [44](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=44) | Hücre gösterimindeki bölmeler, yarı tepkime yönleri ve potansiyel işaretleri birlikte okunmalı. |
| Kimya | AYT 24 | 43 / [45](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=45) | Bağ çokluğu ve atom komşuluğu aynı şey değildir. Yapıdan hibritleşme doğrulayıcısı yok. |
| Biyoloji | TYT 18 | 40 / [42](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_tyt_2026_kitapcik_d350.pdf#page=42) | İki panel ayrı evre dizileri içeriyor. İndeksteki zaman ifadesi burada sürekli zaman ölçeği anlamına gelmiyor. |
| Biyoloji | AYT 28 | 44 / [46](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=46) | Numaralar tek noktaları değil parantezlerle gösterilen uzunlukları tanımlıyor. |
| Biyoloji | AYT 31 | 44 / [46](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=46) | Üç biyolojik önerme için öncül birleşimi tek başına bilimsel kanıt sağlamaz. |
| Biyoloji | AYT 36 | 45 / [47](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=47) | Zincir etiketi, okun yönü ve gösterdiği süreç ayrı kaydedilmeli. Ok yönünün görülmesi yorumunu doğrulamaz. |
| Biyoloji | AYT 37 | 45 / [47](https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/TSK/yks_ayt_2026_kitapcik_kt12.pdf#page=47) | Etiketin hangi yapıya işaret ettiği ve yapının işlevi ayrı değerlendirilir. |

## Uygulamaya yansıyan bulgular

- Matematik görsel okuma talimatı artık panel, eğri veya renkli parçanın basılı etiketiyle eşleşmesini açıkça ister. Bir eğrinin adını bulmak sorunun kendisiyse kimlik açık bırakılır. İfadelerde iç içe kapsam ve anlatı içindeki koşullar korunur.
- Bütünlük denetiminde renk veya ok ucu hangi öğenin sorulduğunu değiştiriyorsa ilgili eski OCR notu hedefli okumaya gider. Dekoratif renk değişikliği olağan akışta kalır. Bir notta kaynaksız bir kategori önce geçiyorsa sonraki geçerli görsel kanıt artık gözden kaçmaz.
- Zorunlu görsel verisi eksikken açıkça grafikten, işaretli bölgeden veya renkli yaydan istenen bilgiyi ilgisiz bir denklem karşılayamaz. Metnin gerçekten yeterli olduğu eski örnek ayrı regresyon testinde korunur.
- Bilimsel kanıt denetiminde doğrudan gözlenen bir okun anlamı ancak kaynak metin veya öğrenci onayıyla destekleniyorsa tam kontrol sonucu alır. Modelleme varsayımıyla sunulan anlam için yalnızca yönün gözlendiği raporlanır.

Bu değişiklikler mevcut matematik hattı ve çevrimdışı bilimsel denetimler üzerinde sınanır. Ücretli Vision değerlendirmesi, model ağırlıklarının eğitimi veya fizik, kimya ve biyoloji için öğrenciye açık bir çözme motoru bu incelemenin sonucu değildir.

## Yerel doğrulama

| Denetim | Sonuç |
| --- | --- |
| Firestore emülatörü ile pytest (\`-W default\`) | 642 geçti, 0 başarısız, 0 atlanan, 173,26 saniye |
| Bütünlük matrisi | 57 senaryo ve 10 seçenek vakası, 0 yanlış engelleme, kritik belirsizlikle ilerleyen 0 senaryo |
| Bilimsel denetim matrisi | 72 sentetik vaka, beklenenden farklı 0 sonuç |
| Önceki özgün soru paketi | 24 soruda 20 sonuç türetilmiş anahtarla uyumlu, 4 çekimser, 0 yanlış |
| Web | Lint ve tür denetimi geçti. 20 test geçti, 14 sayfa derlendi. npm audit 0 bulgu verdi. |
| Diğer kontroller | Ruff, eğitim sözleşmesi güncellik denetimi ve çevrimdışı model veri seti doğrulaması geçti. |

İlk bütünlük matrisi, açıkça okunan tek bilinmeyenli denklemin eşlik ettiği genel şekil atfında gereksiz yeniden okuma gösterdi. Kural somut görsel hedeflerle sınırlandı. Son koşuda mevcut kontrol örneği tek okumada ilerledi.

## Seçim notu

AYT Matematik 23 seçkiye dahil değil. ÖSYM önce cevap değişikliğini, ardından sonuç duyurusunda yargı kararıyla iptalini bildirdi. Tablodaki AYT Fen 23 kimya sorusudur. [İlk duyuru](https://www.osym.gov.tr/2026-yuksekogretim-kurumlari-sinavi-2026yks-degerlendirme-islemleri) · [Sonuç duyurusu](https://www.osym.gov.tr/2026-yks-sonuclari-aciklandi)

İndeksteki 2025 AYT kitapçığı ek kaynaktır ve açılış sayfası doğrulandı. OGM bağlantısı etkinlik kataloğuna gider. Bu iki kaynaktan seçili soru verilmedi.
