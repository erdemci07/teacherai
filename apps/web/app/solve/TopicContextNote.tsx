'use client';

import { useMemo, useSyncExternalStore } from 'react';
import { clearTopicContext, parseTopicContext, rawTopicContext, subscribeTopicContext } from '../lib/topic-context';

// TA-007: Konular ekranından gelen konu bağlamı korunur ve gösterilir. Sunucuya gönderilmez; sınıf ve konu
// sorudan çıkarılmaz. Öğrenci bağlamı tek dokunuşla kaldırabilir.
export function TopicContextNote() {
  const raw = useSyncExternalStore(subscribeTopicContext, rawTopicContext, () => null);
  const context = useMemo(() => parseTopicContext(raw), [raw]);
  if (!context) return null;
  return (
    <p className="taNotice ok" role="status" data-topic-context={context.topicId}>
      Seçtiğin konu: <span className="taCode">{context.code}</span> {context.title} · {context.programLabel}, {context.grade}. sınıf.
      {' '}Bu konudan bir sorunun fotoğrafını yükle.{' '}
      <button type="button" onClick={() => clearTopicContext()}>Konuyu kaldır</button>
    </p>
  );
}
