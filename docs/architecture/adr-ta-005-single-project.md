# ADR TA-005: Tek Firebase projesi ve taşıma araçları

Durum: kabul edildi (kod ve araçlar). Canlı taşıma **yapılmadı**; [runbook](../migration/TA-005-runbook.md) onay bekliyor. Bulgular [denetimdedir](../migration/TA-005-audit.md).

## Bağlam

Bugün kaynaklar iki projeye dağılmış durumda:

- math-ai-07: Cloud Run, Firestore (eur3), Secret Manager, Artifact Registry, Auth ve web uygulamaları
- teacherai-07: yalnızca Hosting sitesi (Spark planı)

Paylaşım kısayolu Hosting'den run.app'e 302 ile gidiyor. Canlı servis `TEACHERAI_ENVIRONMENT` tanımsız olduğu için `development` ortamında çalışıyor ve proje kimliğini koddaki varsayılandan alıyor. Kurallar, indeksler ve TTL politikaları canlıya hiç yayımlanmamış.

## Kararlar

1. **Tek proje kimliği.**
   - `firebase_project_id` için varsayılan değer yoktur.
   - Production'da `firebase_project_id` ile `firebase_auth_project_id` zorunludur ve eşit olmalıdır; aksi hâlde uygulama başlamaz.
   - Cloud Run'da (`K_SERVICE` tanımlıysa) ortam `production` veya `staging` olmalıdır.
   - Proje kimliği dağıtımda tek değişkenden gelir: `deploy-production.ps1` içindeki `$ProjectId` ve Cloud Build'deki `$PROJECT_ID`.
   - Eski proje kimliğinin yalnızca geçiş materyalinde geçtiğini bir sözleşme testi (`git grep`) zorunlu kılar.
2. **Paylaşım rewrite ile, API doğrudan.**
   - `/s/**` aynı projedeki `teacherai-api` servisine Hosting rewrite ile gider. Paylaşım adresi Hosting alan adında kalır.
   - API, Hosting'in 60 saniyelik istek sınırı nedeniyle rewrite'tan geçmez. Bu sınır resmî belgede doğrulandı: https://firebase.google.com/docs/hosting/cloud-run. API doğrudan Cloud Run URL'sinden ve CORS izin listesiyle çağrılır.
   - Projeler arası rewrite'ın desteklendiği belgede yazmadığı için eski model, yani 302 redirect, yalnız geçiş öncesinde geçerliydi.
3. **CORS.** `math-ai-07.web.app` varsayılan izin listesinden çıkarıldı. Gerekçe: site `/` ve `/s/` için 404 döndürüyor ve hiçbir istemci bu kökenden API çağırmıyor.
4. **Bakım modu ve eski bağlantılar.**
   - `TEACHERAI_MAINTENANCE_MODE` değerleri:
     - `off`
     - `read_only`: yazma isteklerine `Retry-After` ile 503 döner. Okuma ve paylaşım görüntüleme çalışır.
     - `redirect`
   - `TEACHERAI_LEGACY_REDIRECT_BASE` tanımlıysa `/s/{id}` istekleri her modda 301 ile yeni adrese gider.
   - Bakım ara katmanı kimlik ve gövde denetiminden önce, CORS katmanının içinde çalışır. Böylece bakım sırasında token doğrulanmaz ve 503 yanıtı tarayıcıya ulaşır.
5. **Veri taşıma betiği** (`scripts/migration/copy_firestore.py`).
   - Varsayılan çalışma kuru koşudur. Yazmak için `--execute --confirm-target <aynı>` gerekir. Hedef eski projeyse ayrıca `--allow-reverse` gerekir.
   - Koleksiyonlar açık bir izin listesiyle seçilir ve her birinin kopyalanma gerekçesi yazılıdır.
   - Kimlikler, alt koleksiyonlar ve tipler korunur.
   - Kopya artımlıdır. Eşitlik yalnız tip etiketli kanonik içerik özetiyle kanıtlanır; TA-005'teki `updated_at` kısayolu TA-005B'de kaldırıldı (aynı damga, farklı içerik "aynı" sayılıyordu).
   - `--verify` iki yönlüdür ve yalnızca sayı döndürür: yalnız kaynakta, yalnız hedefte, farklı, aynı, sahipsiz, Auth'ta olmayan sahip ve silinmiş hesaba ait kalan belge.
   - Betik iki yönde de çalışır. TA-005B uzlaştırma kuralları:
     - `--authority source|target` zorunludur, varsayılanı yoktur.
     - İki taraftaki `account_deletions` kayıtlarının birleşimindeki UID'nin verisi hiçbir yöne yazılmaz.
     - Silme kaydı TTL ile kaybolmuş olabileceği için kullanıcıya ait belge, sahibi yetkili tarafın Auth'unda yoksa yazılmaz.
     - Çakışmada yetkili tarafın değeri kazanır; ezilen ya da yazılmayan içeriğin özeti raporlanır.
     - Hedefte fazla belge otomatik silinmez. Budama yalnız `--prune --confirm-prune <hedef> --prune-from <rapor>` ile, son 1 saatte aynı kaynak/hedef için üretilmiş `--verify` raporunda görülmüş ve o andan beri özeti değişmemiş belgelere uygulanır.
     - Bilinen sınır: kopya, silme kayıtlarını başlangıçta bir kez okur. Kopya sırasında başlayan bir silme, iki tarafın da bakım modunda (`read_only`) olmasına dayanır.
6. **Denetim betiği** (`scripts/migration/audit_projects.py`).
   - Yalnızca okuyan gcloud fiillerine kod düzeyinde izin verir.
   - Auth kullanıcılarını sunucu taraflı alan maskesiyle ister.
   - Çıktıda UID ve e-posta bulunmaz.

## Reddedilenler

- API'yi Hosting rewrite'ı üzerinden geçirmek (60 sn sınırı).
- Auth birleştirmesini otomatikleştirmek. K1(c) çakışma kararını Erdem verir.
- Eski anahtarı kopyalamak. Yeni OpenAI anahtarı ayrı bir projede ve harcama limitiyle oluşturulur.
- Hizmet hesabı anahtarı indirmek.

## Sağlayıcıdan bağımsız geçit (TA-005B'ye kaldı)

Bölüm 7 bu fazda uygulanmadı. Tasarım kısıtları şunlardır:

- Port, `parse_response`'un sonuç sınıflandırmasını, mantıksal çağrı tavanını ve `purpose` alanını korur.
- İşlem bazında `TEACHERAI_PROVIDER_<OPERATION>` ayarı olur. Varsayılan değer `openai`, production'da Anthropic kapalıdır.
- Fiyatlar yapılandırmadan okunur.
- Maliyet duyarlı yönlendirmenin kararı TA-006'da, `evaluate_models pack` verisiyle verilir.

## Sonuçlar

Kod artık yalnızca tek projeyle doğru çalışır. Bu kodla eski canlı servisi yeniden dağıtmak, ortam ayarı yapılmadan **başarısız olur**. Bu bilinçli bir güvenlik kapısıdır. Dağıtım betiği ortam değişkenlerini kendisi ayarlar.
