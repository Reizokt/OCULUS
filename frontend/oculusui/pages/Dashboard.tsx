import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SearchBox } from '../components/SearchBox';
import { TerminalBackground } from '../components/TerminalBackground';
import { PriceChart, SectorMap } from '../blocks';
import { useSearch } from '../data/hooks';
import { IhsgChart } from './ihsgchart';


export default function Dashboard() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const search = useSearch(query);

  return (
    <div>
      <TerminalBackground bleed title="Find a company" subtitle="Search by name or ticker to open its narrative.">
        <SearchBox results={search.data?.results ?? []} onQueryChange={setQuery} onSelect={(t) => navigate(`/company/${t}`)} autoFocus />
      </TerminalBackground>

      <div className="mt-grid">
          <div className="mt-span-8">
            <IhsgChart />
          </div>
        </div>
        <div className="mt-span-4">
          <SectorMap title="Sectors today" onSelect={(s) => navigate(`/company/${s}`)} action={<Link to="/sectors" className="mt-pill">Open map</Link>} />
        </div>
      </div>
  );
}
