import type { Metadata } from 'next';
import './globals.css';
import 'katex/dist/katex.min.css';
import { Footer } from './components/Footer';
import { AuthProvider } from './auth/AuthProvider';
import { Navigation } from './components/Navigation';

export const metadata: Metadata = {
  title: 'TeacherAI | The AI mathematics teacher',
  description: 'TeacherAI creates structured, teacher-quality lessons from student questions.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
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
