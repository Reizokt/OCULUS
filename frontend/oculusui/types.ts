/** Shared contracts between services and micro-frontends. null = "no data yet". */
export type Num = number | null;
export type Unit = 'usd' | 'idr' | 'pct' | 'x';

// ---- company-data service -------------------------------------------------
export interface SearchResult { ticker: string; name: string; sector: string | null }
export interface SearchResponse { results: SearchResult[] }

export interface MetricRow { label: string; value: string | null; change: Num }
export interface MetricGroup { title: string; rows: MetricRow[] }
export interface NarrativeResponse {
  ticker: string;
  name: string;
  sector: string | null;
  metricGroups: MetricGroup[];
}

// ---- market-data service --------------------------------------------------
export interface RankRow { id: string; name: string; value: Num; change7d: Num }
export interface Leaderboard {
  id: string;
  title: string;
  unit: Unit;
  headline: Num;
  headlineLabel: string;
  change30d: Num;
  change90d: Num;
  series: number[];
  leadersLabel: string;
  leaders: RankRow[];
  movers: RankRow[];
  moversLabel?: string;
  moversChangeLabel?: string;
  changeUnit?: Unit;   // unit for the mover change column; defaults to `unit`
}

export type PriceRange = '1M' | '3M' | '1Y' | '5Y';
export interface PricePoint { t: string; v: Num }
export interface PriceResponse {
  symbol: string;
  name: string;
  currency: string;
  range: PriceRange;
  last: Num;
  change: Num;
  points: PricePoint[];
}

export interface SectorStock { symbol: string; name: string; weight: Num; change: Num }
export interface Sector { id: string; name: string; weight: Num; change: Num; stocks: SectorStock[] }
export interface SectorsResponse { period: string; sectors: Sector[] }

// ---- narrative assessment + forecast (company-data) ------------------------
export type Tone = 'bull' | 'bear' | 'neutral';
export interface AssessmentBlock { heading: string; tone: Tone; items: string[] }
export interface Assessment {
  ticker: string;
  verdict: { label: string; tone: Tone } | null;
  summary: string | null;
  blocks: AssessmentBlock[];
  updatedAt: string | null;
  author: string | null;
}

export interface ForecastPeriod { label: string; kind: 'actual' | 'forecast' }
export interface ForecastRow {
  label: string;
  unit: Unit;
  /** one value per period */
  values: Num[];
  /** optional analyst range, per period (forecast columns) */
  low?: Num[];
  high?: Num[];
}
export interface Forecast {
  ticker: string;
  periods: ForecastPeriod[];
  rows: ForecastRow[];
  note: string | null;
}
