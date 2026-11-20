class ShareError(Exception):
    code = "share_error"
    status_code = 500
    public_message = "Paylaşım bağlantısı şu anda oluşturulamadı."


class ShareUnpublishedError(ShareError):
    code = "share_unpublished"
    status_code = 410
    public_message = "Bu paylaşım yayından kaldırıldı."


class ShareStorageError(ShareError):
    code = "share_storage_error"
    status_code = 503
    public_message = "Paylaşım bağlantısı şu anda kalıcı olarak kaydedilemedi."
