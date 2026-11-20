"""Hesap silme yazma engeli.

Kullanıcıya bağlı her kalıcı yazma, aynı Firestore işleminde account_deletions/{uid}
belgesini okur ve belge varsa (durum fark etmez) iptal edilir. Firestore işlemleri
serileştirilebilir olduğundan, silme işareti yazıldıktan sonra commit edilmeye
çalışan uçuştaki bir yazma (ör. önceden kabul edilmiş bir AI isteğinin sonucu)
çakışma nedeniyle yeniden denenir, işareti görür ve hiçbir veri bırakmaz.
"""

from apps.api.app.core.retention import DELETIONS


class AccountDeletionInProgress(Exception):
    """409 / account_deletion_in_progress."""


def ensure_active(db, tx, uid):
    """İşlem içinde çağrılır; okuma, işlemin yazmalarından önce yapılmalıdır."""
    if uid and db.collection(DELETIONS).document(uid).get(transaction=tx).exists:
        raise AccountDeletionInProgress


def deletion_started(db, uid):
    """Kabul aşaması için hızlı ön kontrol. Asıl güvence ensure_active'dir."""
    return bool(db is not None and uid and db.collection(DELETIONS).document(uid).get().exists)
