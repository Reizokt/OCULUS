'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { SearchBox } from '@/components/SearchBox';
import { TerminalBackground } from '@/components/TerminalBackground';
import { PriceChart, SectorMap } from '@/blocks';
import { useSearch } from '@/data/hooks';
import { IhsgChart } from '../../pages/ihsgchart';

export default function Dashboard() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const search = useSearch(query);

  return (
    <>
      <TerminalBackground bleed title="Find a company" subtitle="Search by name or ticker to open its narrative.">
        <SearchBox
          results={search.data?.results ?? []}
          onQueryChange={setQuery}
          onSelect={(t) => router.push(`/company/${t}`)}
          placeholder="Search companies, e.g. BBCA"
          autoFocus
        />
      </TerminalBackground>

      <div className="mt-grid">
        <div className="mt-span-8">
                    <IhsgChart />
                  </div>
        <div className="mt-span-4">
          <SectorMap title="Sectors today" onSelect={(s) => router.push(`/company/${s}`)} action={<Link href="/sectors" className="mt-pill">Open map</Link>} />
        </div>
      </div>
    </>
  );
}