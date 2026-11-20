// Idempotency-Key yönetimi. Saf modüldür; kök TS testlerinden sınanır.
//
// Aynı mantıksal isteğin sonucu bilinmiyorsa (ağ hatası, istemci zaman aşımı) yeniden
// deneme aynı anahtarı kullanır; sunucu bunu ikinci kez kabul etmez ve ücretli işlem
// tekrar çalışmaz. Sunucu yanıt verdiyse (başarı veya hata) sonraki deneme bağımsız
// yeni bir işlemdir ve yeni anahtar alır. Sunucu önceki başarılı yanıtı saklamadığından
// bu "en fazla bir kez çalıştırma" sağlar, "tam olarak bir kez yanıt" garantisi değildir.

export type AttemptOutcome = 'answered' | 'unknown';

const UNKNOWN_CODES = new Set(['network_error', 'request_timeout', 'lesson_timeout']);

export function outcomeOf(code: string | null): AttemptOutcome {
  return code !== null && UNKNOWN_CODES.has(code) ? 'unknown' : 'answered';
}

export class IdempotencyKeys {
  private readonly keys = new Map<string, string>();

  constructor(private readonly create: () => string = () => crypto.randomUUID()) {}

  keyFor(action: string): string {
    let key = this.keys.get(action);
    if (!key) {
      key = this.create();
      this.keys.set(action, key);
    }
    return key;
  }

  settle(action: string, outcome: AttemptOutcome): void {
    if (outcome === 'answered') this.keys.delete(action);
  }
}
