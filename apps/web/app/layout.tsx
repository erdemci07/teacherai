import type { Metadata, Viewport } from 'next';
import './globals.css';
import './design-system.css';
import 'katex/dist/katex.min.css';
import { Footer } from './components/Footer';
import { AuthProvider } from './auth/AuthProvider';
import { Navigation } from './components/Navigation';
import { AppNav } from './components/AppNav';

export const metadata: Metadata = {
  title: 'TeacherAI | Matematiği mantığıyla öğren',
  description: 'Matematik sorunu yükle; TeacherAI matematiksel olarak kontrol edip öğretmen gibi adım adım anlatsın.',
};

// TA-006: güvenli alan (çentik), ekran klavyesi ve tema rengi. Yakınlaştırma kapatılmaz (erişilebilirlik).
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  interactiveWidget: 'resizes-content',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f6f1e7' },
    { media: '(prefers-color-scheme: dark)', color: '#161917' },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body>
        <AuthProvider>
        <Navigation />
        <AppNav />
        <main>{children}</main>
        <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
