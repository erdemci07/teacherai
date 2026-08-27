import Link from 'next/link';
import { BrandMark } from './components/BrandMark';

const teacherSteps = [
  { step: '01', title: 'Soruyu anlar', text: 'Fotoğraftaki matematik ifadesini ve ne istendiğini çıkarır.' },
  { step: '02', title: 'Adım adım çözer', text: 'İşlemleri sıraya koyar, önemli kuralları atlamaz.' },
  { step: '03', title: 'Öğretmen gibi anlatır', text: 'Cevabın neden öyle olduğunu sade bir dille açıklar.' },
];

const quickCards = [
  { title: 'Kamerayla çek', text: 'Sorunun fotoğrafını çek', icon: '📷', primary: true },
  { title: 'Galeriden seç', text: 'Fotoğraf yükle', icon: '🖼️', primary: false },
];

export default function Home() {
  return (
    <main className="mobileHome">
      <section className="homeBrandCard appEntryBrand" aria-label="TeacherAI giriş">
        <BrandMark size="lg" decorative={false} className="entryMascot" />
        <div className="entryBrandCopy">
          <h1>TeacherAI</h1>
          <p>Senin yapay zekâ öğretmenin</p>
        </div>
      </section>

      <section className="homeSolveCard appEntryHero" aria-labelledby="home-solve-title">
        <p className="eyebrow">Matematik öğretmenin yanında</p>
        <h2 id="home-solve-title">Sorunu göster, birlikte çözelim.</h2>
        <p>Kamerayla çek veya galeriden seç. TeacherAI önce soruyu anlar, sonra çözümü nedenleriyle anlatır.</p>
        <div className="homeActionStack" aria-label="Soru yükleme başlangıcı">
          {quickCards.map((card) => (
            <Link className={`homeActionCard ${card.primary ? 'homeActionPrimary' : ''}`} href="/solve" key={card.title}>
              <span aria-hidden="true">{card.icon}</span>
              <strong>{card.title}</strong>
              <small>{card.text}</small>
            </Link>
          ))}
        </div>
        <Link className="primaryButton homeSolveButton" href="/solve">Soru Çözmeye Başla</Link>
      </section>

      <section className="homeHelperCard teacherFlowCard" aria-labelledby="teacherai-after-title">
        <div className="teacherFlowHeader">
          <div>
            <span>TeacherAI sonra ne yapar?</span>
            <h2 id="teacherai-after-title">Cevabı değil, mantığını öğren.</h2>
          </div>
        </div>
        <ol>
          {teacherSteps.map((item) => (
            <li key={item.step}>
              <span>{item.step}</span>
              <div>
                <strong>{item.title}</strong>
                <small>{item.text}</small>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
