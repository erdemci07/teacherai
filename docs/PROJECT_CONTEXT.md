# TeacherAI proje bağlamı

TeacherAI genel amaçlı, çok disiplinli bir öğretmendir. Amaç, öğrencinin karşılaştığı bir sonraki soruyu bağımsız çözebilmesidir. Sınav hedefi öğrenci bağlamının isteğe bağlı bir alanıdır. Çalışan öğrenci akışları değişiklikler sırasında korunur.

| Durum | Kapsam |
| --- | --- |
| Uygulandı | Next.js/React/TypeScript öğrenci arayüzü, FastAPI/Pydantic modüler monoliti, Firebase Auth, Firestore, matematik görseli analizi, yapılandırılmış ders, BoardPlanner, KaTeX, ders sonrası etkileşim, geçmiş ve bağlantıyla paylaşım. TA-001 değişiklikleri yerel dalda doğrulanır. |
| Kısmi | MathAI sınırlı tek değişkenli gerçel denklemleri ve belirli grafik özelliklerini denetler. Sözel gerekçeler otomatik olarak kanıtlanmaz. Doğrulanabilir benzer denklem üretildiğinde öğrenci pratik yanıtı gönderebilir. Öğrenme hafızası mevcut etkileşim olaylarından oluşur. |
| Planlandı | Müfredat modülü ilgili eski programları ve Türkiye Yüzyılı Maarif Modeli’ni destekleyecek. Sınıf düzeyine uygun yöntemler açık politikalarla uygulanacak. Öğretmen bilgisi yapılandırılacak ve bağımsız incelemeden geçecek. Mobil istemci için ilk tercih Capacitor. |
| Ertelendi | Yeni bilim alanları, ek AI sağlayıcıları, Öğretmen Stüdyosu, canlı ses ve cihaz entegrasyonu sonraki fazlarda ele alınacak. |
| Dış doğrulama bekliyor | Gerçek sağlayıcı kalite karşılaştırması, dağıtılmış sürüm, gerçek Firebase kimliği ve App Check geçişi. |

## Mimari ve sözleşme

Sağlayıcı → yapılandırılmış LessonPlan → doğrulama → renderer → öğrenci. Sağlayıcı değiştirilebilir. Tahta elemanlarını oluşturmak BoardPlanner’ın sorumluluğudur. Güvenlik, bilimsel doğruluk, maliyet ölçümü ve testler her modülde geliştirme koşuludur. Fiziksel dizinler çalışan modüller ihtiyaç duydukça gelişir.

Çalışan sözleşme Python modellerinde ve FastAPI OpenAPI çıktısındadır. LessonPlan v1, kaynak analizi, kavram, öğrenme hedefleri ve içeriği taşır. GeneratedLesson zarfı doğrulama sonucu, tahta ve süreleri taşır. Mimari taslaktaki ses, video, öğretmen değerlendirmesi ve veri kümesi alanları geleceğe aittir. Kök src/ ve tests/ altındaki TypeScript örneği ayrı bir mimari prototiptir. Gelecekte web tiplerini FastAPI OpenAPI bileşenlerinden üreterek CI’da şema farkları incelenmelidir. Uyumsuz bir sözleşme ayrı bir sürüm ve geçiş planı gerektirir.

## Kalıcı veri ve dağıtım

Cloud Run ve mevcut Firestore yapılandırması math-ai-07, Firebase Hosting teacherai-07 ve bölge us-east4 olarak korunur. Web uygulamasının gerçek Firebase Auth projesini web kaydından doğrulayın. Sunucu kimlik kitlesi ve Firestore proje seçimi ayrı ayarlanabilir. Paylaşım kısayolu Hosting üzerinden Cloud Run’a yönlenir. Müşteri verisi, gizli anahtarlar ve canlı servis çağrıları olağan CI testlerine girmez.

Kabul sonuçları, istemci geçişi, yapılandırma ve açık konular [TA-001 faz raporunda](phase-reports/TA-001.md) yer alır.
