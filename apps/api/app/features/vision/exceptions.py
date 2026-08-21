class VisionError(Exception):
    code = "vision_error"
    status_code = 500
    public_message = "Soru görseli işlenemedi. Lütfen tekrar deneyin."


class MissingImageError(VisionError):
    code = "image_required"
    status_code = 400
    public_message = "Lütfen bir soru görseli seçin."


class UnsupportedImageError(VisionError):
    code = "unsupported_image_type"
    status_code = 415
    public_message = "Yalnızca JPG, JPEG, PNG, WEBP, HEIC veya HEIF görselleri desteklenir."


class ImageTooLargeError(VisionError):
    code = "image_too_large"
    status_code = 413
    public_message = "Görsel izin verilen dosya boyutunu aşıyor."


class InvalidImageError(VisionError):
    code = "invalid_image"
    status_code = 422
    public_message = "Görsel okunamadı. Geçerli bir JPG, PNG, WEBP, HEIC veya HEIF dosyası yükleyin."


class ProviderConfigurationError(VisionError):
    code = "provider_not_configured"
    status_code = 503
    public_message = "Görsel analiz servisi henüz yapılandırılmamış."


class ProviderAuthenticationError(VisionError):
    code = "provider_not_configured"
    status_code = 503
    public_message = "Görsel analiz servisi henüz yapılandırılmamış."


class ProviderRateLimitError(VisionError):
    code = "provider_unavailable"
    status_code = 503
    public_message = "Görsel analiz servisi şu anda yoğun. Lütfen biraz sonra tekrar deneyin."


class ProviderUnavailableError(VisionError):
    code = "provider_unavailable"
    status_code = 503
    public_message = "Görsel analiz servisine şu anda ulaşılamıyor. Lütfen tekrar deneyin."


class ProviderTimeoutError(VisionError):
    code = "provider_timeout"
    status_code = 504
    public_message = "Görsel analizi zaman aşımına uğradı. Lütfen tekrar deneyin."


class InvalidProviderResponseError(VisionError):
    code = "invalid_provider_response"
    status_code = 502
    public_message = "Görsel analizi tamamlanamadı. Lütfen daha net bir görselle tekrar deneyin."
