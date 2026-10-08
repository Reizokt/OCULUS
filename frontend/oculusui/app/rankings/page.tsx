'use client';

import { Ranking } from '@/blocks';

export default function Rankings() {
  return (
    <div className="mt-grid">
      <div className="mt-span-4"><Ranking metric="Brokers" /></div>
      <div className="mt-span-4"><Ranking metric="Sectors" /></div>
      <div className="mt-span-4"><Ranking metric="Top Stocks" /></div>
    </div>
  );
}