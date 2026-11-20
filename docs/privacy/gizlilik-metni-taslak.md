# TeacherAI gizlilik metni — TASLAK

> **Bu metin taslaktır.** Bir hukukçu tarafından incelenmemiş ve onaylanmamıştır. KVKK ve ilgili mevzuata uyum tamamlanmış değildir. Köşeli parantez içindeki alanlar proje sahibi ve hukuk danışmanı tarafından doldurulmalıdır. Metin, 20 Kasım 2026 tarihli `ta-001b` dalındaki gerçek kod davranışına göre hazırlandı. Kod değiştikçe bu metin de güncellenmelidir.

## 1. Veri sorumlusu ve iletişim

- Veri sorumlusu: **[işletmeci unvanı — doğrulanmadı, doldurulacak]**
- Adres ve iletişim: **[doldurulacak]**
- Başvuru kanalı: **[doldurulacak]**

## 2. İşlenen veri kategorileri

| Kategori | Ne içerir | Nereden gelir |
| --- | --- | --- |
| Hesap bilgileri | E-posta adresi, Firebase kullanıcı kimliği (uid), isteğe bağlı görünen ad ve sınav hedefi | Kayıt ve profil formu |
| Soru görselleri | Yüklediğin fotoğraf veya ekran görüntüsü | Çözüm ekranı |
| Analiz sonuçları | Görselden çıkarılan soru metni, matematiksel ifadeler ve konu bilgisi | Görsel analiz servisi |
| Çözüm geçmişi | Üretilen ders anlatımı, doğrulama sonucu, tahta içeriği, soru özeti | Ders üretimi |
| Öğrenme kayıtları | Etkileşim olayları (ipucu, sadeleştirme vb.), pratik soruları ve yanıtların, öğrenme hafızası özetleri | Ders sonrası etkileşim |
| Geri bildirim | Değerlendirme, gerekçeler, isteğe bağlı yorum, ilgili model ve sürüm bilgisi | Geri bildirim formu |
| Paylaşım bağlantıları | Yalnız işlem adımları ve matematiksel sonuç. Fotoğraf, ham soru metni ve serbest anlatım yeni paylaşımlara konmaz. | Paylaşım düğmesi |
| Kullanım sayaçları | Günlük işlem ve token sayıları. Kimlik yerine uid’in SHA-256 özetiyle tutulur. | Her AI isteği |
| Teknik kayıtlar | İstek kimliği, işlem türü, model, token ve süre ölçümleri, hata türü. Görsel, soru metni, istem ve kimlik belirteci bu kayıtlara yazılmaz. | Sunucu günlükleri |

## 3. İşleme amaçları

- Yüklenen sorunun analiz edilmesi ve adım adım anlatım üretilmesi
- Çözümün matematiksel doğrulamadan geçirilmesi
- Öğrenme geçmişinin ve kişiselleştirilmiş ipuçlarının sunulması
- Kötüye kullanımın ve maliyetin sınırlanması (günlük kotalar, küresel bütçe)
- Hizmet kalitesinin geri bildirimle iyileştirilmesi
- Güvenlik, hata ayıklama ve hesap silme taleplerinin yerine getirilmesi

**Hukuki dayanak:** [doldurulacak — her amaç için hukukçu tarafından belirlenmeli; bu taslak bir dayanak önermez]

## 4. Hizmet sağlayıcılar ve yurt dışı aktarım

| Sağlayıcı | Kullanım | Konum ve aktarım notu |
| --- | --- | --- |
| Google Firebase ve Google Cloud | Kimlik doğrulama (Firebase Auth), veritabanı (Firestore), web barındırma (Hosting), API sunucusu (Cloud Run) | API sunucusu `us-east4` (ABD) bölgesinde. Firestore veritabanı konumu **[doğrulanmadı]**. |
| OpenAI | Görsel analizi, ders anlatımı ve etkileşim yanıtlarının üretilmesi. Görsel ve ilgili metin işleme için gönderilir. İsteklerde `store=false` kullanılır. | ABD. OpenAI’nin API veri saklama koşulları **[güncel sözleşmeden doğrulanmalı]**. |
| Resend (yalnız etkinse) | Kritik geri bildirimlerin işletmeciye e-postayla bildirilmesi | **[etkinleştirilmeden önce doğrulanmalı]** |
| Google reCAPTCHA Enterprise / App Check (yalnız etkinse) | Uygulama doğrulaması | **[etkinleştirilmeden önce doğrulanmalı]** |

Bu sağlayıcıların bir kısmı Türkiye dışındadır, bu nedenle veriler yurt dışına aktarılır. **Yurt dışı aktarımın hukuki dayanağı ve gerekli işlemler (ör. açık rıza, standart sözleşme, bildirim) açık konudur ve hukukçu tarafından belirlenmelidir.**

## 5. Saklama süreleri

| Veri | Süre |
| --- | --- |
| Soru görseli | Analiz süresince geçici dosya olarak tutulur, analiz bitince silinir. Kalıcı olarak saklanmaz. |
| Analiz sonucu | 24 saat. Süresi geçen kayıt hemen kullanılamaz hale gelir. Fiziksel silme Firestore TTL ile gecikmeli yapılır. |
| Pratik sorusu | 1 saat yanıtlanabilir, 7 gün saklanır |
| Kullanım sayaçları | 30 gün |
| Çözüm geçmişi, öğrenme kayıtları, etkileşim olayları, pratik yanıtları, profil, öğrenme hafızası, geri bildirim, paylaşımlar | Otomatik silinmez. Hesap silinene kadar saklanır. |
| Hesap silme kaydı | Silme tamamlandıktan sonra 30 gün. Yalnız uid ve işlem durumu içerir. |
| Teknik kayıtlar | **[Cloud Logging saklama süresi doğrulanmalı]** |
| Yedekler | **[Firestore yedekleme veya geri alma ayarı doğrulanmalı]** |

Not: TTL özelliği yalnız saklama alanı taşıyan yeni kayıtlara uygulanır. Bu özellikten önce oluşmuş bazı kayıtlar ayrıca ele alınmadıkça süresiz kalabilir.

## 6. Hesap silme

Ayarlar sayfasındaki **Hesabımı sil** bölümünden, e-posta ve parolanla yeniden doğrulama yaptıktan sonra hesabını silebilirsin. Silinenler:

- profil ve hesap bilgileri, Firebase oturum hesabı,
- çözüm geçmişi, analizler, öğrenme hafızası,
- pratik soruları, yanıtlar ve etkileşim olayları,
- oluşturduğun paylaşım bağlantıları ve geri bildirimler,
- kullanım sayaçları.

Silme başladıktan sonra hesabına yeni kayıt yazılamaz. Önceden başlamış bir istek de yeni kayıt bırakamaz. Eski sürümde sahibi kaydedilmeden oluşturulmuş bazı paylaşım bağlantıları otomatik silinemez. Bunlar işletmeci incelemesiyle yayından kaldırılır. Yayından kaldırılan bağlantı ara bellekte en çok 5 dakika görünür kalabilir.

## 7. Haklarına ilişkin bilgi

İlgili mevzuat kapsamındaki haklarını kullanmak için **[başvuru kanalı — doldurulacak]** üzerinden başvurabilirsin. Uygulama içinden şu anda yapılabilenler: öğrenme hafızasını sıfırlama, geçmişi görüntüleme ve hesabı tamamen silme. Verilerin bir kopyasını dışa aktarma özelliği **henüz yoktur**.

**Hakların listesi, başvuru süreci ve süreleri:** [hukukçu tarafından doldurulacak]

## 8. Çocuk kullanıcılar — açık konular

TeacherAI öğrencilere yöneliktir ve kullanıcıların bir kısmı reşit olmayabilir. Aşağıdaki konularda **henüz karar verilmemiştir**:

- asgari yaş sınırı ve yaş doğrulama yöntemi,
- veli veya vasi onayının gerekip gerekmediği ve nasıl alınacağı,
- okul veya öğretmen aracılığıyla kullanımda rollerin dağılımı,
- çocuklara yönelik bu metnin sade bir sürümü.

Bu kararlar verilmeden reşit olmayan kullanıcılara yönelik geniş çaplı yayın önerilmez.

## 9. Güncellemeler

Bu metin değiştiğinde yürürlük tarihi güncellenir. **[yürürlük tarihi — doldurulacak]**
