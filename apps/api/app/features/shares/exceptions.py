class ShareError(Exception):
    code = "share_error"
    status_code = 500
    public_message = "Paylaşım bağlantısı şu anda oluşturulamadı."


class ShareStorageError(ShareError):
    code = "share_storage_error"
    status_code = 503
    public_message = "Paylaşım bağlantısı şu anda kalıcı olarak kaydedilemedi."
