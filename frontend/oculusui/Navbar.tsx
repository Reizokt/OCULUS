'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/rankings', label: 'Rankings' },
  { href: '/sectors', label: 'Sector map' },
];

export default function Navbar() {
  const pathname = usePathname();
  return (
    <div className="mt-nav">
      <Link href="/dashboard" className="mt-brand"><span className="mt-brand-mark" />OCULUS</Link>
      <nav className="mt-links" aria-label="Main">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={`mt-link${pathname === l.href || pathname.startsWith(l.href + '/') ? ' active' : ''}`}>{l.label}</Link>
        ))}
      </nav>
    </div>
  );
}
