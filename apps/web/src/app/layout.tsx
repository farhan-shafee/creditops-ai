import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'CreditOps AI | Synthetic trading operations',
  description:
    'Independent incident intelligence portfolio project. Synthetic telemetry, read-only investigation, evidence-backed RCA, and reproducible evaluations.',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
