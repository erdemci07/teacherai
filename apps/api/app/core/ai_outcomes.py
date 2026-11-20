"""Sağlayıcı çağrısı sonuç sınıfları (TA-001B, B paketi).

Her sağlayıcı çağrısı tam olarak bir sonuca düşer. ai_usage günlüğündeki
"outcome" alanı bu adları taşır. Başarısız sonuçlarda hiçbir kayıt kalıcı hale
gelmez; hata, kalıcı yazmayı yapan yönlendirici kodundan önce fırlatılır.
"""

from enum import StrEnum


class Outcome(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE_MAX_TOKENS = "incomplete_max_tokens"
    INCOMPLETE_OTHER = "incomplete_other"
    REFUSAL = "refusal"
    INVALID_OUTPUT = "invalid_output"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"


class AIOutcomeError(Exception):
    """Gateway'in sınıflandırdığı başarısız sağlayıcı sonucu."""

    outcome = Outcome.PROVIDER_ERROR
    status_code = 502
    code = "ai_provider_error"
    public_message = "Öğretmen servisi yanıt veremedi. Biraz sonra yeniden deneyebilirsin."

    def __init__(self, reason: str | None = None):
        super().__init__(self.code)
        self.reason = reason


class AIOutputTruncatedError(AIOutcomeError):
    outcome = Outcome.INCOMPLETE_MAX_TOKENS
    status_code = 502
    code = "ai_output_truncated"
    public_message = "Yanıt yarıda kaldığı için gösteremiyorum. Aynı soruyu yeniden deneyebiliriz."


class AIOutputFilteredError(AIOutcomeError):
    outcome = Outcome.INCOMPLETE_OTHER
    status_code = 422
    code = "ai_output_filtered"
    public_message = "Bu içerik için güvenli bir anlatım hazırlayamadım. Farklı bir soruyla devam edebiliriz."


class AIOutputIncompleteError(AIOutcomeError):
    """Bilinmeyen incomplete nedeni; içerik filtresi sayılmaz, gerçek neden günlüğe yazılır."""

    outcome = Outcome.INCOMPLETE_OTHER
    status_code = 502
    code = "ai_output_incomplete"
    public_message = "Yanıt tamamlanamadı. Biraz sonra yeniden deneyebilirsin."


class AIRefusalError(AIOutcomeError):
    outcome = Outcome.REFUSAL
    status_code = 422
    code = "ai_refused"
    public_message = "Bu isteğe yardımcı olamadım. Sorunun yalnızca matematik kısmını gönderebilir misin?"


class AIInvalidOutputError(AIOutcomeError):
    outcome = Outcome.INVALID_OUTPUT
    status_code = 502
    code = "ai_invalid_output"
    public_message = "Güvenilir bir yanıt oluşturamadım. Aynı soruyu yeniden deneyebiliriz."


class AITimeoutError(AIOutcomeError):
    outcome = Outcome.TIMEOUT
    status_code = 504
    code = "ai_timeout"
    public_message = "Yanıt beklediğimden uzun sürdü. Biraz sonra yeniden deneyebilirsin."


# Rezervasyon kuralı: tüketimi bilinmeyen sonuçlarda rezervasyon korunur.
KEEP_RESERVATION = {Outcome.TIMEOUT}
