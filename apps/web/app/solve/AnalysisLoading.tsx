'use client';

import { useEffect, useState } from 'react';

const stages: Record<string, { primary: string; secondary?: string; detail: string; checklist: string }> = {
  uploading: { primary: 'Görsel hazırlanıyor...', secondary: 'Dosya güvenli şekilde yükleniyor...', detail: 'Fotoğrafı incelemeye hazırlıyorum.', checklist: 'Görsel alınıyor' },
  analyzing: { primary: 'Soruyu okuyorum...', secondary: 'Şekil ve ifadeleri dikkatlice inceliyorum...', detail: 'Bu aşamada yalnızca sorunun içeriği çıkarılıyor.', checklist: 'Soruyu anlıyor' },
  planning: { primary: 'Çözüm yolunu planlıyorum...', secondary: 'Adımları kontrol ediyorum...', detail: 'Öğretmen anlatımı matematiksel olarak denetleniyor.', checklist: 'Çözüm planı kuruluyor' },
  rendering: { primary: 'Anlatımı hazırlıyorum...', detail: 'Çözüm birazdan ekranda olacak.', checklist: 'Anlatım hazırlanıyor' },
};
const order = ['uploading', 'analyzing', 'planning', 'rendering'];

export function AnalysisLoading({ uploading, stage }: { uploading: boolean; stage?: string }) {
  const key = uploading ? 'uploading' : stage ?? 'analyzing';
  const [showSecondary, setShowSecondary] = useState(false);
  const current = stages[key] ?? stages.analyzing;
  const activeIndex = Math.max(0, order.indexOf(key));

  useEffect(() => {
    setShowSecondary(false);
    if (!current.secondary) return;
    const timer = window.setTimeout(() => setShowSecondary(true), 7000);
    return () => window.clearTimeout(timer);
  }, [key, current.secondary]);

  return (
    <div className="analysisLoading teacherThinkingCard" role="status" aria-live="polite">
      <div className="loadingMascotWrap">
        <img src="/teacherai-mascot.png" alt="" />
        <span className="loadingSpinner" aria-hidden="true" />
      </div>
      <div className="thinkingContent">
        <span className="loadingEyebrow">TeacherAI düşünüyor</span>
        <strong>{showSecondary && current.secondary ? current.secondary : current.primary}</strong>
        <p>{current.detail}</p>
        <ul className="loadingSteps teacherChecklist">
          {order.map((item, index) => (
            <li className={index < activeIndex ? 'done' : index === activeIndex ? 'active' : ''} key={item}>
              {stages[item].checklist}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
