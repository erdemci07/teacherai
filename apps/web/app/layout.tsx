import type { Metadata } from 'next';
import './globals.css';
import 'katex/dist/katex.min.css';
import { Footer } from './components/Footer';
import { AuthProvider } from './auth/AuthProvider';
import { Navigation } from './components/Navigation';

export const metadata: Metadata = {
  title: 'TeacherAI | Matematiği mantığıyla öğren',
  description: 'Matematik sorunu yükle; TeacherAI matematiksel olarak kontrol edip öğretmen gibi adım adım anlatsın.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body>
        <AuthProvider>
        <Navigation />
        <main>{children}</main>
        <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
