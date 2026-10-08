// Fictional demo data. Nothing here is real market data.
// Replace the bodies of these functions with real API calls later (see hooks.ts).
import type {
  Assessment, Forecast, Leaderboard, NarrativeResponse, PricePoint, PriceRange, PriceResponse, SearchResult, SectorsResponse,
} from '../types';

function rng(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const hash = (s: string) => s.split('').reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7);

export const COMPANIES: SearchResult[] = [
  { ticker: 'ACME', name: 'Acme Industrial', sector: 'Industrials' },
  { ticker: 'GLBX', name: 'Globex Systems', sector: 'Technology' },
  { ticker: 'INIT', name: 'Initech Software', sector: 'Technology' },
  { ticker: 'SPY', name: 'Index Fund', sector: null },
];

export function searchCompanies(q: string): SearchResult[] {
  const s = q.toLowerCase();
  return COMPANIES.filter((c) => c.ticker.toLowerCase().includes(s) || c.name.toLowerCase().includes(s));
}

const DAYS: Record<PriceRange, number> = { '1M': 30, '3M': 90, '1Y': 365, '5Y': 1825 };

export function getPrices(symbol: string, range: PriceRange): PriceResponse {
  const r = rng(hash(symbol));
  let v = 60 + r() * 140;
  const now = Date.now();
  const all: PricePoint[] = Array.from({ length: 1825 }, (_, i) => {
    v *= 1 + (r() - 0.48) * 0.025;
    return { t: new Date(now - (1824 - i) * 864e5).toISOString().slice(0, 10), v: +v.toFixed(2) };
  });
  const points = all.slice(-DAYS[range]);
  const first = points[0].v as number;
  const last = points[points.length - 1].v as number;
  const name = COMPANIES.find((c) => c.ticker === symbol)?.name ?? symbol;
  return { symbol, name, currency: 'USD', range, last, change: (last / first - 1) * 100, points };
}

export function getSectors(): SectorsResponse {
  const r = rng(7);
  const names: Array<[string, string]> = [['tech', 'Technology'], ['health', 'Health care'], ['fin', 'Financials'], ['disc', 'Consumer discretionary'], ['comm', 'Communication'], ['ind', 'Industrials'], ['staples', 'Consumer staples'], ['energy', 'Energy'], ['util', 'Utilities'], ['re', 'Real estate'], ['mat', 'Materials']];
  return {
    period: '1D',
    sectors: names.map(([id, name]) => {
      const stocks = Array.from({ length: 5 + Math.floor(r() * 6) }, (_, i) => ({ symbol: `${id.slice(0, 3).toUpperCase()}${i + 1}`, name: `${name} ${i + 1}`, weight: 1 + r() ** 2 * 40, change: (r() - 0.5) * 6 }));
      const weight = stocks.reduce((a, s) => a + (s.weight ?? 0), 0);
      return { id, name, weight, change: stocks.reduce((a, s) => a + (s.change ?? 0) * (s.weight ?? 0), 0) / weight, stocks };
    }),
  };
}

const BOARDS: Record<string, { title: string; unit: 'usd' | 'count'; scale: number }> = {
  aum: { title: 'Client assets', unit: 'usd', scale: 9e12 },
  commission: { title: 'Commission revenue', unit: 'usd', scale: 4e9 },
  accounts: { title: 'Active accounts', unit: 'count', scale: 2e7 },
};

export function getRanking(metric: string): Leaderboard | null {
  const b = BOARDS[metric];
  if (!b) return null;
  const r = rng(hash(metric));
  const leaders = 'ABCDEFGHIJ'.split('').map((l, i) => ({ id: `${metric}${i}`, name: `Broker ${l}`, value: b.scale * (0.4 / (i + 1) + 0.02), change7d: b.scale * (r() - 0.4) * 0.004 }));
  let v = b.scale * 0.7;
  return {
    id: metric, title: b.title, unit: b.unit, headline: leaders.reduce((a, x) => a + x.value, 0), headlineLabel: 'Latest',
    change30d: 4.1, change90d: 10.3, series: Array.from({ length: 80 }, () => (v *= 1 + (r() - 0.46) * 0.04)),
    leadersLabel: 'Market leaders', leaders, movers: [...leaders].sort((a, b2) => b2.change7d - a.change7d),
  };
}

export function getCompany(ticker: string): NarrativeResponse {
  const c = COMPANIES.find((x) => x.ticker === ticker);
  return {
    ticker, name: c?.name ?? ticker, sector: c?.sector ?? null,
    metricGroups: [
      { title: 'Key metrics', rows: [{ label: 'Revenue (TTM)', value: '$12.4 B', change: 8.1 }, { label: 'Net income (TTM)', value: '$1.4 B', change: 11.2 }, { label: 'Free cash flow (TTM)', value: '$1.1 B', change: -3.4 }] },
      { title: 'Valuation metrics', rows: [{ label: 'Market cap', value: '$38.2 B', change: 2.4 }, { label: 'P/E', value: '27.3x', change: -1.2 }, { label: 'EV/EBITDA', value: '16.8x', change: 0.6 }] },
    ],
  };
}

export function getAssessment(ticker: string): Assessment {
  return {
    ticker,
    verdict: { label: 'Constructive', tone: 'bull' },
    summary: 'Sells automation hardware and recurring service contracts. Services now carry most of the margin growth, so the story is shifting from unit sales to attach rate. The assessment holds as long as service renewals stay above 90%.',
    blocks: [
      { heading: 'Thesis', tone: 'bull', items: ['Service revenue compounds faster than hardware', 'Backlog covers roughly two quarters of sales', 'Operating margin has widened four quarters in a row'] },
      { heading: 'Risks', tone: 'bear', items: ['Two customers make up a third of revenue', 'Component costs could reverse the margin gain', 'Renewal pricing is untested in a downturn'] },
      { heading: 'Catalysts', tone: 'neutral', items: ['Q4 guidance in January', 'New contract tier launching next quarter'] },
    ],
    updatedAt: '2026-10-01',
    author: 'Research desk',
  };
}

export function getForecast(ticker: string): Forecast {
  const periods: Forecast['periods'] = [
    { label: 'FY23', kind: 'actual' }, { label: 'FY24', kind: 'actual' }, { label: 'FY25', kind: 'actual' },
    { label: 'FY26E', kind: 'forecast' }, { label: 'FY27E', kind: 'forecast' }, { label: 'FY28E', kind: 'forecast' },
  ];
  const row = (label: string, start: number, g: number): Forecast['rows'][number] => {
    const values = periods.map((_, i) => start * (1 + g) ** i);
    return {
      label, unit: 'usd', values,
      low: values.map((v, i) => (periods[i].kind === 'forecast' ? v * 0.94 : null)),
      high: values.map((v, i) => (periods[i].kind === 'forecast' ? v * 1.06 : null)),
    };
  };
  return { ticker, periods, rows: [row('Revenue', 9.8e9, 0.09), row('EBITDA', 1.6e9, 0.12), row('Net income', 0.9e9, 0.14), row('EPS', 2.1, 0.13)], note: 'Consensus of 12 analysts' };
}
