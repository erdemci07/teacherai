// API hata kodlarının öğrenciye gösterilen Türkçe karşılıkları.
// Saf modüldür; tarayıcı ya da Firebase bağımlılığı yoktur ve kök testlerden doğrudan sınanır.

export const ERROR_MESSAGES: Readonly<Record<string, string>> = {
  authentication_required: 'Soru çözmek için oturum aç.',
  usage_limit_exceeded: 'Günlük kullanım sınırına ulaştın.',
  image_required: 'Lütfen bir soru görseli seç.',
  unsupported_image_type: 'Bu dosya türünü okuyamıyorum. JPG, JPEG, PNG, WEBP, HEIC veya HEIF biçiminde bir görsel deneyebilir misin?',
  image_too_large: 'Bu görsel 10 MB sınırını aşıyor. Daha küçük bir fotoğraf seçebilir misin?',
  invalid_image: 'Bu görseli okuyamadım. Sorunun tamamının net göründüğü başka bir fotoğraf deneyebilir misin?',
  image_sanitization_failed: 'Bu fotoğrafı analiz için güvenli biçime dönüştüremedim. Aynı soruyu yeniden çekip gönderebilir misin?',
  provider_not_configured: 'Öğretmen servisi henüz hazır değil. Biraz sonra tekrar deneyebilirsin.',
  provider_unavailable: 'Şu anda öğretmen servisine ulaşamıyorum. Biraz sonra tekrar deneyebilirsin.',
  provider_timeout: 'Görsel analizi beklediğimden uzun sürdü. Aynı görselle yeniden deneyebiliriz.',
  invalid_provider_response: 'Görseldeki soruyu güvenilir biçimde çıkaramadım. Daha net bir fotoğraf deneyebilir misin?',
  lesson_provider_not_configured: 'Öğretmen servisi henüz hazır değil. Biraz sonra tekrar deneyebilirsin.',
  lesson_provider_unavailable: 'Anlatımı şu anda hazırlayamadım. Biraz sonra yeniden deneyebilirsin.',
  invalid_lesson_plan: 'Çözüm taslağı güvenilir biçimde oluşmadı. Aynı soruyu yeniden inceleyebiliriz.',
  lesson_context_too_large: 'Bu sorunun içeriği oldukça yoğun olduğu için anlatımı hazırlayamadım. Yeniden incelemeyi deneyebilirsin.',
  math_verification_failed: 'Çözümü matematiksel kontrolden geçiremedim. Aynı soruyla yeniden deneyebiliriz.',
  subject_generation_unavailable: 'Bu soruyu tanıdım ama bu alanda ders anlatımı henüz hazır değil. Şimdilik matematik ve geometri sorularında yardımcı olabilirim.',
  question_clarification_required: 'Soruyu çözmeden önce okuyamadığım bir kısmı netleştirmemiz gerekiyor.',
  stale_question_revision: 'Soru bu arada güncellendi. Güncel hâliyle yeniden deneyelim.',
  invalid_clarification: 'Bu seçimi kaydedemedim. Seçenekleri yeniden görüp tekrar deneyebilirsin.',
  question_not_pending: 'Bu soru için bekleyen bir netleştirme kalmadı.',
  analysis_unavailable: 'Bu soru analizinin süresi dolmuş. Görseli yeniden gönderebilirsin.',
  ai_call_budget_exhausted: 'Bu soru için ek inceleme hakkı doldu. Daha net bir fotoğrafla yeniden deneyebilirsin.',
  verification_contradiction: 'Bu çözüm matematiksel kontrolden geçmedi. Soruyu yeniden inceleyelim.',
  lesson_timeout: 'İnceleme beklediğimden uzun sürdü. Tekrar deneyebilir misin?',
  network_error: 'Şu anda TeacherAI’a ulaşamıyorum. İnternet bağlantını kontrol edip yeniden deneyebilirsin.',
  lesson_error: 'Çözümü şu anda hazırlayamadım. Biraz sonra yeniden deneyebilirsin.',
  // B paketi: sağlayıcı sonuç sınıfları. Yarım içerik hiçbir koşulda gösterilmez.
  ai_output_truncated: 'Yanıt yarıda kaldığı için gösteremiyorum. Aynı soruyu yeniden deneyebiliriz.',
  ai_output_filtered: 'Bu içerik için güvenli bir anlatım hazırlayamadım. Farklı bir soruyla devam edebiliriz.',
  ai_output_incomplete: 'Yanıt tamamlanamadı. Biraz sonra yeniden deneyebilirsin.',
  ai_refused: 'Bu isteğe yardımcı olamadım. Sorunun yalnızca matematik kısmını gönderebilir misin?',
  ai_invalid_output: 'Güvenilir bir yanıt oluşturamadım. Aynı soruyu yeniden deneyebiliriz.',
  ai_timeout: 'Yanıt beklediğimden uzun sürdü. Biraz sonra yeniden deneyebilirsin.',
  ai_provider_error: 'Öğretmen servisi yanıt veremedi. Biraz sonra yeniden deneyebilirsin.',
  // Aynı Idempotency-Key ile tekrar: ücretli işlem ikinci kez çalıştırılmadı.
  duplicate_request: 'Bu istek zaten alındı. Sonuç geçmişinde görünüyorsa oradan açabilirsin; yoksa yeniden deneyebilirsin.',
  account_deletion_in_progress: 'Hesabın silinme sürecinde olduğu için bu işlem yapılamıyor.',
  // C paketi: günlük küresel AI kapasitesi doldu.
  ai_global_budget_exhausted: 'Öğretmen servisi bugünlük kapasitesine ulaştı. Yarın yeniden deneyebilirsin.',
  // TA-005: proje taşıma dönemi (503, Retry-After).
  maintenance_read_only: 'TeacherAI kısa bir bakımda. Şu an yeni soru gönderilemiyor; geçmişin ve paylaşımların açık. Birkaç dakika sonra yeniden dene.',
  service_moved: 'TeacherAI yeni adresine taşındı. Sayfayı yenileyip yeniden dene.',
};

export const DEFAULT_ERROR_MESSAGE = 'Bir sorun oluştu. Biraz sonra yeniden deneyebilirsin.';

export function errorMessage(code: string | null | undefined): string {
  return (code && ERROR_MESSAGES[code]) || DEFAULT_ERROR_MESSAGE;
}
