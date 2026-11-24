// TA-007: "Bu konudan soru çöz" eyleminde seçilen konu bağlamı soru çözme ekranına taşınır. Yalnız gösterim
// içindir: sunucuya gönderilmez, sınıf veya konu sorudan çıkarılmaz ve ders üretimini değiştirmez.
export interface TopicContext { programId: string; programLabel: string; grade: number; topicId: string; code: string; title: string }

const KEY = 'teacherai.topicContext';

interface StorageLike { getItem(key: string): string | null; setItem(key: string, value: string): void; removeItem(key: string): void }

function storage(): StorageLike | null {
  try { return typeof window === 'undefined' ? null : window.sessionStorage; } catch { return null; }
}

export function isTopicContext(value: unknown): value is TopicContext {
  if (!value || typeof value !== 'object') return false;
  const item = value as Record<string, unknown>;
  return ['programId', 'programLabel', 'topicId', 'code', 'title'].every((key) => typeof item[key] === 'string' && (item[key] as string).length <= 300)
    && typeof item.grade === 'number' && Number.isInteger(item.grade) && item.grade >= 1 && item.grade <= 12;
}

export function saveTopicContext(context: TopicContext, store: StorageLike | null = storage()): void {
  store?.setItem(KEY, JSON.stringify(context));
}

export function parseTopicContext(raw: string | null): TopicContext | null {
  try {
    const value: unknown = JSON.parse(raw ?? 'null');
    return isTopicContext(value) ? value : null;
  } catch { return null; }
}

export function readTopicContext(store: StorageLike | null = storage()): TopicContext | null {
  return parseTopicContext(store?.getItem(KEY) ?? null);
}

const EVENT = 'teacherai-topic-context';

// useSyncExternalStore için: ham değer (kararlı dize) ve değişiklik aboneliği.
export function rawTopicContext(): string | null {
  return storage()?.getItem(KEY) ?? null;
}

export function subscribeTopicContext(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => undefined;
  window.addEventListener('storage', callback);
  window.addEventListener(EVENT, callback);
  return () => { window.removeEventListener('storage', callback); window.removeEventListener(EVENT, callback); };
}

export function clearTopicContext(store: StorageLike | null = storage()): void {
  store?.removeItem(KEY);
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENT));
}
