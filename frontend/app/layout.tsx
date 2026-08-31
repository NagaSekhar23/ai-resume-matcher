import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Resume Matcher',
  description: 'Local-first resume matching and recruiter-style analysis.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
