import Link from 'next/link';

export const metadata = { title: 'Gizlilik | TeacherAI' };

export default function Page() {
  return <div className="pageShell narrow"><div className="panel">
    <p className="eyebrow">Gizlilik</p>
    <h1>Verilerin ve hakların</h1>
    <p>Soru görselleri çözüm sırasında geçici olarak işlenir ve analizden sonra silinir. Analiz ve anlatım üretimi için görsel ve ilgili metin yapay zekâ hizmet sağlayıcısına gönderilir.</p>
    <p>Hesabınla kaydedilen çözüm geçmişini ve öğrenme bilgilerini panelinden görebilir, öğrenme hafızanı sıfırlayabilirsin. Hesabını ve verilerini Ayarlar sayfasından kalıcı olarak silebilirsin.</p>
    <p>Ayrıntılı gizlilik metni hazırlanmaktadır.</p>
    <div className="placeholderActions">
      <Link className="primaryButton" href="/dashboard">Panelime git</Link>
      <Link className="secondaryButton" href="/settings">Ayarlar</Link>
    </div>
  </div></div>;
}
