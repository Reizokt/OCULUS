import { Ranking } from '../blocks';

export default function Rankings() {
  return (
    <div className="mt-grid">
      {/* Copy-paste a cell to add a ranking. `metric` must exist in services/market-data/src/data.ts */}
      <div className="mt-span-4"><Ranking metric="aum" /></div>
      <div className="mt-span-4"><Ranking metric="commission" /></div>
      <div className="mt-span-4"><Ranking metric="accounts" /></div>
    </div>
  );
}
