# TA-007 denetimli geri getirme mimarisi

Modül: `apps/api/app/features/knowledge/retrieval.py`. Çağıran: `curriculum/context.py → select`. Saf Python; vektör veritabanı, gömme, ücretli API veya ek model çağrısı yoktur.

## Akış

```
soru (OCR metni + ifade AST'si)
  → topics.map_question          aday konular + kanıt düzeyi (structural / single / ambiguous / none)
  → registry_v2.resolve          program, sınıf, izlek, sınav kapsamı
  → match_outcomes               kazanım: konu anahtarı > takma ad > taksonomi deseni
  → retrieval.retrieve           aday bilgi girdileri, uygunluk, bütçe
  → methods.select               yetkili onaylı yöntem politikaları
  → CurriculumContextPayload     isteme giden sınırlı bağlam
  → EducationalProvenance        seçim + dışlama + (sağlayıcıdan sonra) gerçek iletim
```

## Dizinler ve sıralama

Kayıt nesnesi başına bir kez kurulan dizin (`index_for`, kimlik denetimli önbellek): kazanım bağı, konu anahtarı, müfredat başlığı bağı, başlık+ifade sözcükleri.

| Sinyal | Puan | Not |
| --- | --- | --- |
| Kazanım bağı (`outcome_refs`) | 16 | Yalnız kazanım cümlesi görülerek doğrulanmış bağlar |
| Konu anahtarı (taksonomi `knowledge_topics`) | 8 | |
| Müfredat başlığı bağı (`curriculum_topic_refs`) | 4 | |
| Önkoşul/ilişki (tek adım) | 2 | Yalnız başka sinyalle gelmiş girdiden |
| Hafif sözcük örtüşmesi (≥ 2 sözcük) | 1 | Yalnız sıralamayı etkiler; tek başına girdi getirmez |

Eşitlikte kimlik sırası. Alan filtresi: matematik ↔ geometri ortak; diğer alanlar karışmaz.

## Kipler

- `production`: yalnız `runtime_eligibility` boş girdiler. Ders akışı yalnız bu kipi kullanır. Uygun olmayanlar `not_runtime_eligible` nedeniyle dışlananlara yazılır.
- `preview`: taslaklar engelleriyle birlikte; `as_context` önizleme sonucunu reddeder, böylece isteme giremez. Çevrimdışı önizleme için `python -m scripts.knowledge_registry preview <kimlik>`.

## Paketleme ve bütçe

`Budget(max_entries=3, max_record_bytes=700, max_total_bytes=1400)`; toplam bağlam `MAX_PAYLOAD_BYTES = 2600`. Kural: **kırpma yok, dışarıda bırakma var.**

1. Kayıt bütünüyle paketlenir: ifade, bütün koşullar, varsayımlar, istisnalar.
2. Kayıt sınırı aşılırsa önce isteğe bağlı yanılgı listesi çıkarılır ve kayıt `compacted_knowledge` listesine yazılır.
3. Yine sığmazsa kayıt `exceeds_record_budget` ile dışlanır; toplam sınırda `exceeds_total_budget`; sayı sınırında `limit_reached`.
4. Toplam bağlam sınırında önce son bilgi kaydı bütünüyle, sonra son kazanım çıkarılır.

## Köken

`EducationalProvenance`: `selection_mode`, `topic_mapping`, `topic_candidates`, `knowledge_ids`, `knowledge_refs` (kimlik + sürüm + içerik özeti), `excluded_knowledge` (nedenli), `compacted_knowledge`, `method_policy_ids`, `inactive_method_policies`, `verification_capabilities`, `transmission`, `transmitted_knowledge_ids`. Acil sıkıştırmada (`context_level="emergency"`) müfredat/bilgi bağlamı gönderilmez; kayıt seçimi korur, iletimi boş yazar.

## Güvenlik

- Bilgi metni isteme veri olarak girer; sağlayıcı bu bağlamdan doğrulama, onay veya müfredat kararı üretemez (sunucu denetimleri ayrıdır).
- Kaynak ve katkı metinlerindeki talimat benzeri içerik etkisizdir: yalnız onaylı (insan incelemesinden geçmiş) girdiler bağlama girer ve sağlayıcı çıktısı her durumda doğrulanır.
- Değerlendirme anahtarları ve bağımsız sorular (`evals/`) bağlama girmez; `dataset_manifest --check` örtüşmeyi reddeder. Öğretmen katkıları (`data/contributions`) çalışma zamanında okunmaz.

## Ölçümler (geliştirme makinesi, 2026-11-25)

| İşlem | Süre |
| --- | --- |
| Müfredat kaydı yükleme (bir kez) | ≈ 490 ms |
| Bilgi kaydı yükleme (bir kez) | ≈ 315 ms |
| Taksonomi yükleme | ≈ 25 ms |
| `select` (tam bağlam seçimi) | ≈ 2,9 ms/çağrı |
| `retrieve` | ≈ 0,16 ms/çağrı |
| `map_question` | ≈ 2,6 ms/çağrı |
