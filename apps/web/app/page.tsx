import Link from 'next/link';

const steps = [
  'Sorunu yükle',
  'Soruyu anlar',
  'Matematiği kontrol eder',
  'Öğretmen gibi anlatır',
  'Anlamadıysan farklı açıklar',
];

const benefits = [
  { icon: '✎', title: 'Öğretmen Gibi Anlatır', description: 'Soruyu sadece çözmez; kullanılan kuralı, yöntemi ve kritik noktaları açıklar.' },
  { icon: '✓', title: 'MathAI ile Kontrol Eder', description: 'Desteklenen matematiksel işlemleri bağımsız olarak doğrular.' },
  { icon: '◌', title: 'Seni Zamanla Tanır', description: 'Çözümlerinden ve çalışma davranışlarından yararlanarak anlatımı sana göre uyarlayabilir.' },
  { icon: '↗', title: 'Eksiklerini Fark Eder', description: 'Hata örüntülerini ve zorlandığın konuları takip ederek neye çalışman gerektiğini anlamana yardımcı olur.' },
];

const faqs = [
  { question: 'TeacherAI yalnızca cevabı mı verir?', answer: 'Hayır. Hangi kuralın kullanıldığını, adımların neden yapıldığını ve dikkat etmen gereken noktaları anlatır.' },
  { question: 'Hangi soruları yükleyebilirim?', answer: 'JPG, PNG veya WEBP biçimindeki okul, LGS, TYT, AYT ve diğer matematik sorularını yükleyebilirsin.' },
  { question: 'Çözümüm kaydedilir mi?', answer: 'Hesabınla giriş yaparsan geçmiş çözümlerine dönebilir ve TeacherAI anlatımını çalışma davranışlarına göre uyarlayabilir.' },
];

export default function Home() {
  return <>
    <section className="hero betaHero">
      <div className="heroContent">
        <p className="eyebrow">Matematiği gerçekten öğren</p>
        <h1>Matematik sorunu yükle. <span>Cevabı değil, mantığını öğren.</span></h1>
        <p className="heroText">TeacherAI sorunu analiz eder, matematiksel olarak kontrol eder ve gerçek bir öğretmen gibi adım adım anlatır.</p>
        <div className="heroActions"><Link className="primaryButton" href="/solve">Sorunu Çöz</Link><a className="secondaryButton" href="#nasil-calisir">Nasıl Çalışır?</a></div>
        <p className="heroTrust">Fotoğrafını çek veya galeriden seç. İlk sorunu hemen deneyebilirsin.</p>
      </div>
      <div className="teacherPreview" aria-label="TeacherAI örnek anlatım görünümü">
        <span className="previewBadge">TeacherAI</span><h2>Adım adım, nedenleriyle.</h2>
        <div className="previewNote">Ne arıyoruz?<strong>x'i yalnız bırakmak</strong></div>
        <div className="previewEquation">3x + 7 = 19</div><div className="previewArrow">↓ iki taraftan 7 çıkar</div><div className="previewEquation result">x = 4 <b>✓</b></div>
      </div>
    </section>
    <section className="section" id="nasil-calisir"><div className="sectionHeader"><p className="eyebrow">TeacherAI nasıl çalışır?</p><h2>Sorudan anlamaya, beş net adım.</h2></div><div className="stepsGrid betaSteps">{steps.map((step,index)=><article className="stepCard" key={step}><span>{index+1}</span><h3>{step}</h3></article>)}</div></section>
    <section className="section altSection"><div className="sectionHeader"><p className="eyebrow">Neden TeacherAI?</p><h2>Çözümü görmek yetmez. Mantığını kur.</h2></div><div className="featureGrid">{benefits.map(x=><article className="featureCard" key={x.title}><span className="benefitIcon" aria-hidden="true">{x.icon}</span><h3>{x.title}</h3><p>{x.description}</p></article>)}</div></section>
    <section className="section faqSection"><div className="sectionHeader"><p className="eyebrow">Merak ettiklerin</p><h2>Kısaca TeacherAI.</h2></div><div className="faqList">{faqs.map(x=><article className="faqItem" key={x.question}><h3>{x.question}</h3><p>{x.answer}</p></article>)}</div></section>
    <section className="section homeCta"><h2>Bir soruyla başlayalım.</h2><p>Fotoğrafını yükle; TeacherAI mantığını adım adım anlatsın.</p><Link className="primaryButton" href="/solve">Sorunu Çöz</Link></section>
  </>;
}
