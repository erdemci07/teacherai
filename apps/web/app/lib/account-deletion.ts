// Hesap silme durumunun arayüz karşılığı. Saf modüldür; kök TS testlerinden sınanır.

export type DeletionStatus = 'pending' | 'in_progress' | 'completed' | 'failed';
export type DeletionView =
  | { kind: 'working'; message: string }
  | { kind: 'done'; message: string }
  | { kind: 'error'; message: string; canRetry: boolean };

const STEP_LABELS: Readonly<Record<string, string>> = {
  auth: 'oturum hesabı',
  completion_record: 'tamamlanma kaydı',
};

export function deletionView(status: DeletionStatus | null, failedStep: string | null = null, error: string | null = null): DeletionView {
  if (error === 'reauthentication_required') {
    return { kind: 'error', message: 'Güvenlik için e-posta ve parolanla yeniden doğrulaman gerekiyor.', canRetry: true };
  }
  if (error === 'network_error') {
    return { kind: 'error', message: 'Bağlantı kesildi. Silme durumu kontrol edilip kaldığı yerden sürdürülecek.', canRetry: true };
  }
  if (status === 'completed') {
    return { kind: 'done', message: 'Hesabın ve tüm verilerin silindi. Ana sayfaya yönlendiriliyorsun.' };
  }
  if (status === 'failed') {
    const step = failedStep ? STEP_LABELS[failedStep] ?? 'veri' : 'veri';
    return { kind: 'error', message: `Silme ${step} adımında tamamlanamadı. Silinen veriler geri gelmez; tekrar deneyerek kaldığı yerden sürdürebilirsin.`, canRetry: true };
  }
  if (status === 'pending' || status === 'in_progress') {
    return { kind: 'working', message: 'Verilerin siliniyor. Bu işlem birkaç dakika sürebilir, sayfayı kapatma.' };
  }
  return { kind: 'error', message: 'Silme başlatılamadı. Biraz sonra yeniden deneyebilirsin.', canRetry: true };
}

export const DELETED_DATA = [
  'Profilin ve hesap bilgilerin',
  'Çözüm geçmişin, analizlerin ve öğrenme hafızan',
  'Pratik soruların, yanıtların ve etkileşim kayıtların',
  'Oluşturduğun paylaşım bağlantıları ve geri bildirimlerin',
  'Kullanım sayaçların ve oturum hesabın',
];
