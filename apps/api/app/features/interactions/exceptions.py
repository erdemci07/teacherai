class InteractionError(Exception):
    code="interaction_error";status_code=500;public_message="Öğretmen yanıtı oluşturulamadı. Lütfen tekrar deneyin."
class InteractionProviderError(InteractionError):
    code="interaction_provider_unavailable";status_code=503
class InteractionContextTooLargeError(InteractionError):
    code="interaction_context_too_large";status_code=422;public_message="Bu çözüm çok ayrıntılı olduğu için ek öğretmen yanıtı hazırlanamadı."
class InvalidInteractionResponseError(InteractionError):
    code="invalid_interaction_response";status_code=502;public_message="Öğretmen yanıtı güvenilir biçimde hazırlanamadı."
class InvalidInteractionError(InteractionError):
    code="invalid_interaction";status_code=422;public_message="Bu etkileşim desteklenmiyor."
class PracticeNotFoundError(InteractionError):
    code="practice_not_found";status_code=404;public_message="Alıştırma süresi dolmuş. Yeni bir alıştırma başlatın."
class InvalidPracticeError(InteractionError):
    code="invalid_practice";status_code=502;public_message="Güvenilir bir alıştırma oluşturulamadı."
