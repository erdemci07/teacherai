'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getPublicShare, PublicShare } from '../lib/share-api';
import { LessonText } from '../solve/LessonText';
import { RichMathText } from '../solve/RichMathText';
import { TeacherBoardView } from '../solve/TeacherBoard';

export default function SharedSolutionPage() {
  const [share, setShare] = useState<PublicShare | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) { setError(true); return; }
    getPublicShare(id).then(setShare).catch(() => setError(true));
  }, []);

  if (error) {
    return <main className="publicSolutionPage"><section className="publicSolutionHero"><p className="eyebrow">TeacherAI</p><h1>Çözüm bulunamadı</h1><p>Bu paylaşım bağlantısı artık kullanılamıyor olabilir.</p><Link className="primaryButton" href="/solve">Sen de soru çöz</Link></section></main>;
  }

  if (!share) {
    return <main className="publicSolutionPage"><section className="publicSolutionHero"><p className="eyebrow">TeacherAI</p><h1>Çözüm yükleniyor</h1><p>Paylaşılan çözüm hazırlanıyor.</p></section></main>;
  }

  const snapshot = share.snapshot;
  return (
    <main className="publicSolutionPage">
      <section className="publicSolutionHero">
        <p className="eyebrow">TeacherAI</p>
        <h1>Bu soru TeacherAI ile adım adım çözüldü.</h1>
        <p>Çözüm yolunu inceleyebilir, ardından kendi sorunu TeacherAI'a gösterebilirsin.</p>
        <Link className="primaryButton" href="/solve">Sen de soru çöz</Link>
      </section>
      <section className="publicQuestion" aria-labelledby="public-question-title">
        <div>
          <p className="eyebrow">{snapshot.subtopic ? `${snapshot.topic} · ${snapshot.subtopic}` : snapshot.topic}</p>
          <h2 id="public-question-title">Soru</h2>
        </div>
        <p><RichMathText text={snapshot.question_summary} /></p>
      </section>
      <TeacherBoardView board={snapshot.board_snapshot} />
      <LessonText lesson={snapshot.lesson_snapshot} />
      <section className="publicFinalAnswer" aria-labelledby="public-final-answer-title">
        <h2 id="public-final-answer-title">Sonuç</h2>
        <p><RichMathText text={snapshot.final_answer} /></p>
        <Link className="primaryButton" href="/solve">Sen de soru çöz</Link>
      </section>
    </main>
  );
}
