import Link from 'next/link';

const teacherSteps = [
  'Soruyu anlar',
  'Adım adım çözer',
  'Öğretmen gibi anlatır',
];

const quickCards = [
  { title: 'Kamerayla çek', text: 'Soruyu net kadraja al, TeacherAI incelemeye başlasın.' },
  { title: 'Galeriden seç', text: 'Hazır fotoğrafını yükleyip çözüm yolunu gör.' },
];

export default function Home() {
  return (
    <main className="mobileHome">
      <section className="homeBrandCard" aria-label="TeacherAI giriş">
        <img src="/teacherai-mascot.png" alt="TeacherAI maskotu" />
        <h1>TeacherAI</h1>
        <p>Senin yapay zekâ öğretmenin</p>
      </section>

      <section className="homeSolveCard" aria-labelledby="home-solve-title">
        <p className="eyebrow">Hemen başlayalım</p>
        <h2 id="home-solve-title">Matematik sorunu göster</h2>
        <p>Birlikte adım adım çözelim.</p>
        <Link className="primaryButton homeSolveButton" href="/solve">Soruyu Çöz</Link>
        <div className="homeQuickGrid" aria-label="Yükleme seçenekleri">
          {quickCards.map((card) => (
            <article key={card.title}>
              <strong>{card.title}</strong>
              <span>{card.text}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="homeHelperCard" aria-labelledby="teacherai-after-title">
        <div>
          <img src="/teacherai-mascot.png" alt="" />
          <div>
            <span>TeacherAI sonra ne yapar?</span>
            <h2 id="teacherai-after-title">Çözümü sadece vermem, anlatırım.</h2>
          </div>
        </div>
        <ol>
          {teacherSteps.map((step) => <li key={step}>{step}</li>)}
        </ol>
      </section>
    </main>
  );
}
