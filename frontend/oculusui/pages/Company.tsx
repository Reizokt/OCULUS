import { useParams } from 'react-router-dom';
import { Assessment, Forecast, Metrics, PriceChart } from '../blocks';
import { useCompany } from '../data/hooks';

export default function Company() {
  const ticker = (useParams().ticker ?? '').toUpperCase();
  const { data } = useCompany(ticker);

  return (
    <div className="mt-company">
      <aside><Metrics ticker={ticker} /></aside>

      <div>
        <div className="mt-company-head" style={{ marginBottom: 16 }}>
          <h1>{data?.name ?? ticker}</h1>
          <span className="mt-chip mt-up">{ticker}</span>
          {data?.sector && <span className="mt-muted">{data.sector}</span>}
        </div>

        <div className="mt-grid">
          {/* Copy-paste a cell to add a block. */}
          <div className="mt-span-12"><Assessment ticker={ticker} /></div>
          <div className="mt-span-12"><PriceChart symbol={ticker} /></div>
          <div className="mt-span-12"><Forecast ticker={ticker} /></div>
        </div>
      </div>
    </div>
  );
}
