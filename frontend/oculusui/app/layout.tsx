import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import Navbar from '@/Navbar';
import './globals.css';

export const metadata: Metadata = {
  title: 'OCULUS',
  description: 'Market Terminal UI',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="mt-app">
          <Navbar />
          <div className="mt-main">{children}</div>
        </div>
      </body>
    </html>
  );
}
