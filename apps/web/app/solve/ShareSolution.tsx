'use client';

import { useEffect, useState } from 'react';
import { createShare, SHARE_COPY } from '../lib/share-api';
import type { GeneratedLesson } from '../lib/lesson-api';

export function ShareSolution({ result }: { result: GeneratedLesson }) {
  const [shareId, setShareId] = useState<string | undefined>();
  const [shareUrl, setShareUrl] = useState('');
  const [status, setStatus] = useState('');
  const [fallbackUrl, setFallbackUrl] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setShareId(undefined);
    setShareUrl('');
    setStatus('');
    setFallbackUrl('');
  }, [result.lesson.lesson_plan_id]);

  const copyFallback = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setStatus(SHARE_COPY.copied);
      setFallbackUrl('');
    } catch {
      setStatus(SHARE_COPY.copied);
      setFallbackUrl(url);
    }
  };

  const share = async () => {
    setBusy(true);
    setStatus('');
    setFallbackUrl('');
    try {
      const created = await createShare(result, shareId);
      setShareId(created.share_id);
      setShareUrl(created.share_url);
      const payload = { title: 'TeacherAI', text: SHARE_COPY.text, url: created.share_url };
      if (typeof navigator.share === 'function') {
        try {
          await navigator.share(payload);
          setStatus(SHARE_COPY.created);
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') return;
          await copyFallback(created.share_url);
        }
        return;
      }
      await copyFallback(created.share_url);
    } catch {
      setStatus(SHARE_COPY.failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="shareSolution" aria-labelledby="share-solution-title">
      <div>
        <h3 id="share-solution-title">Bu çözümü paylaş</h3>
        <p>Çözüm yolunu bağlantı olarak gönderebilirsin.</p>
      </div>
      <button type="button" className="secondaryButton shareButton" onClick={share} disabled={busy} aria-label="Bu çözümü paylaş">
        {busy ? 'Hazırlanıyor...' : 'Bu çözümü paylaş ↗'}
      </button>
      <p className="shareStatus" aria-live="polite">{status}</p>
      {fallbackUrl && <input className="shareUrlFallback" readOnly value={fallbackUrl || shareUrl} onFocus={(event) => event.currentTarget.select()} aria-label="Paylaşım bağlantısı" />}
    </section>
  );
}
