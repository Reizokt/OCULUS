'use client';

import { useRouter } from 'next/navigation';
import { SectorMap } from '@/blocks';

export default function Sectors() {
  const router = useRouter();
  return (
    <div className="mt-grid">
      <div className="mt-span-12"><SectorMap size="full" onSelect={(symbol) => router.push(`/company/${symbol}`)} /></div>
    </div>
  );
}
