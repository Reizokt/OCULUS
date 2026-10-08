'use client';

// Live data layer. Same hook names and { data, error } shape as the mock version,
// so no component or page needs to change. Needs: npm i swr
import { useMemo } from 'react';
import useSWR from 'swr';
import { fmtValue } from '../lib/format';
import type {
  Assessment, AssessmentBlock, Forecast, Leaderboard, MetricGroup, NarrativeResponse, Num,
  PriceRange, PriceResponse, RankRow, SearchResult, SectorsResponse,
} from '../types';

const BASE = `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api`;

// The backend now returns { data: null } when upstream failed or came back empty (HIT_ONCE mode),
// so `data` can be null on a 200 response.
type Envelope<T> = { data: T | null; meta: { cached: boolean; fetched_at: string; ttl: number } };
type Result<T> = { data: T | null; error: string | null; loading?: boolean };

async function fetchApi<T>(path: string): Promise<Envelope<T>> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * SWR dedupes identical keys, so several blocks on one page share a single request.
 * Revalidation is switched off: the backend already caches in Redis, and while testing
 * every extra request is a chance to burn credits.
 * `env`  = full envelope (for meta), `data` = payload only (null when backend had nothing).
 */
function useApi<T>(path: string | null) {
  const { data: env, error } = useSWR<Envelope<T>>(path, (k: string) => fetchApi<T>(k), {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    revalidateIfStale: false,
    shouldRetryOnError: false,
  });
  return {
    env: env ?? null,
    data: (env?.data ?? null) as T | null,
    error: error ? (error as Error).message : null,
    loading: path !== null && !env && !error,
  };
}

// ---------- helpers ----------
const tk = (s: string) => s.replace(/\.JK$/i, '').toUpperCase(); // UI shows BBCA, backend accepts BBCA or BBCA.JK
const num = (v: unknown): Num => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const human = (k: string) => k.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
const plain = (v: number) => (Math.abs(v) >= 1000 ? fmtValue(v, 'idr') : String(+v.toFixed(2)));

// ---------- companies (search + sector map) ----------
interface CompanyRow {
  symbol: string;
  name: string | null;
  sub_sector: string | null;
  market_cap: number | null;
  chg: number | null;
  chg_w?: number | null;
}
const useCompanyRows = (enabled = true) => useApi<CompanyRow[]>(enabled ? '/companies' : null);

export const useSearch = (q: string): Result<{ results: SearchResult[] }> => {
  const { data: all, error } = useCompanyRows(!!q);
  const data = useMemo(() => {
    if (!q || !Array.isArray(all)) return null;
    const s = q.toLowerCase();
    const hits = all.filter((c) => c.symbol.toLowerCase().includes(s) || (c.name ?? '').toLowerCase().includes(s));
    hits.sort((a, b) => Number(tk(b.symbol).toLowerCase().startsWith(s)) - Number(tk(a.symbol).toLowerCase().startsWith(s)));
    return {
      results: hits.slice(0, 8).map((c) => ({ ticker: tk(c.symbol), name: c.name ?? c.symbol, sector: c.sub_sector })),
    };
  }, [q, all]);
  return { data, error };
};

export const useSectors = (): Result<SectorsResponse> => {
  const { data: all, error } = useCompanyRows();
  const data = useMemo<SectorsResponse | null>(() => {
    if (!Array.isArray(all)) return null;
    const rows = all.filter((r) => r.sub_sector && r.market_cap !== null && r.chg !== null);
    if (rows.length === 0) return null;
    // If the API returns ratios (0.012) instead of percents (1.2), scale to percent.
    const maxAbs = Math.max(0, ...rows.map((r) => Math.abs(r.chg as number)));
    const k = maxAbs > 0 && maxAbs < 0.5 ? 100 : 1;

    const groups = new Map<string, CompanyRow[]>();
    rows.forEach((r) => groups.set(r.sub_sector as string, [...(groups.get(r.sub_sector as string) ?? []), r]));

    const sectors = [...groups.entries()]
      .map(([name, list]) => {
        const sorted = [...list].sort((a, b) => (b.market_cap as number) - (a.market_cap as number));
        const weight = sorted.reduce((a, r) => a + (r.market_cap as number), 0);
        const change = sorted.reduce((a, r) => a + (r.chg as number) * k * (r.market_cap as number), 0) / weight;
        return {
          id: name, name, weight, change,
          stocks: sorted.slice(0, 8).map((r) => ({
            symbol: tk(r.symbol), name: r.name ?? r.symbol, weight: r.market_cap, change: (r.chg as number) * k,
          })),
        };
      })
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 24);
    return { period: '1D', sectors };
  }, [all]);
  return { data, error };
};

// ---------- prices ----------
const BARS: Record<PriceRange, number> = { '1M': 22, '3M': 65, '1Y': 250, '5Y': 500 }; // 5Y = all bars the API gives (max 500)
interface PriceRow { date: string; Close: number | null }

export const usePrices = (symbol: string, range: PriceRange): Result<PriceResponse> => {
  const s = tk(symbol);
  const { data: rows, error } = useApi<PriceRow[]>(`/stocks/${s}/price?bars=500`); // one fetch; ranges are sliced client-side
  const companies = useCompanyRows();
  const data = useMemo<PriceResponse | null>(() => {
    if (!Array.isArray(rows) || rows.length === 0) return null;
    const points = rows.slice(-BARS[range]).map((r) => ({ t: String(r.date).slice(0, 10), v: num(r.Close) }));
    const first = points[0]?.v ?? null;
    const last = points[points.length - 1]?.v ?? null;
    const name = companies.data?.find((c) => tk(c.symbol) === s)?.name ?? s;
    return { symbol: s, name, currency: 'IDR', range, last, change: first && last ? (last / first - 1) * 100 : null, points };
  }, [rows, range, s, companies.data]);
  return { data, error };
};

// ---------- fundamentals -> metrics sidebar ----------
type Fund = Record<string, unknown>;

const ACRONYMS = new Set(['roe', 'roa', 'pe', 'pb', 'pbv', 'npl', 'car', 'ldr', 'nim', 'eps', 'ttm', 'dd', 'cagr', 'casa', 'yoy']);
const MULTIPLES = new Set(['pe', 'pb', 'pbv', 'ps', 'peg', 'ev_ebitda']);

const label = (k: string) =>
  k.split('_').map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1))).join(' ');

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);

const fmtRp = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1e12) return `Rp ${(v / 1e12).toFixed(1)}T`;
  if (a >= 1e9) return `Rp ${(v / 1e9).toFixed(1)}B`;
  return `Rp ${v.toLocaleString('en-US')}`;
};

const fmtMetric = (key: string, v: unknown): string | null => {
  const n = num(v);
  if (n === null) return null;
  return MULTIPLES.has(key) ? `${n.toFixed(1)}x` : `${(n * 100).toFixed(1)}%`;
};

function metricGroups(f: Fund, fallback?: { market_cap?: number | null }): MetricGroup[] {
  const groups: MetricGroup[] = [];

  const price = num(f.price);
  const mcap = num(f.market_cap) ?? fallback?.market_cap ?? null;
  const market: MetricGroup['rows'] = [];
  if (price !== null) market.push({ label: 'Price', value: fmtRp(price), change: null });
  if (mcap !== null) market.push({ label: 'Market cap', value: fmtRp(mcap), change: null });
  if (market.length) groups.push({ title: 'Market', rows: market });

  const scores: MetricGroup['rows'] = [];
  const overall = num(f.fundamental_score);
  if (overall !== null) scores.push({ label: 'Overall', value: `${overall}/100`, change: null });
  if (isObj(f.pillar_scores)) {
    for (const [k, v] of Object.entries(f.pillar_scores)) {
      const n = num(v);
      if (n !== null) scores.push({ label: label(k), value: String(n), change: null });
    }
  }
  const cov = num(f.data_coverage);
  if (cov !== null) scores.push({ label: 'Data coverage', value: `${Math.round(cov * 100)}%`, change: null });
  if (scores.length) groups.push({ title: 'Scores', rows: scores });

  if (isObj(f.pillars)) {
    for (const [k, p] of Object.entries(f.pillars)) {
      if (!isObj(p) || !isObj(p.metrics)) continue;
      const rows = Object.entries(p.metrics).map(([name, m]) => ({
        label: label(name),
        value: (isObj(m) ? fmtMetric(name, m.value) : null) ?? '—',
        change: null,
      }));
      if (rows.length) groups.push({ title: label(k), rows });
    }
  }
  return groups;
}

export const useCompany = (ticker: string): Result<NarrativeResponse> => {
  const t = tk(ticker);
  const { data: f, error } = useApi<Fund>(`/stocks/${t}/fundamentals`);
  const companies = useCompanyRows();
  const data = useMemo<NarrativeResponse | null>(() => {
    if (!f) return null;
    const row = companies.data?.find((c) => tk(c.symbol) === t);
    const sector = (f.sub_sector ?? f.sector ?? row?.sub_sector) as string | undefined;
    const groups = metricGroups(f, { market_cap: row?.market_cap ?? null });
    console.log('[useCompany]', { keys: Object.keys(f), groups }); // temporary, remove once it works
    return {
      ticker: t,
      name: typeof f.name === 'string' ? f.name : row?.name ?? t,
      sector: sector ?? null,
      metricGroups: groups,
    };
  }, [f, companies.data, t]);
  return { data, error };
};

// ---------- narrative + fundamentals -> assessment ----------
interface Narr {
  sentiment?: { label?: string; n_articles?: number };
  themes?: Record<string, number>;
  insider?: { bias?: string };
  upcoming?: { date: string; title: string }[];
  flags?: unknown[];
  event_alignment?: string;
  top_headlines?: string[];
}
const flagText = (f: unknown) => (typeof f === 'string' ? f : JSON.stringify(f));

// ---------- RAG summary -> assessment ----------
type Rag = Record<string, unknown>;
type Tone = 'bull' | 'bear' | 'neutral';

// ---------- RAG summary -> assessment ----------
interface RagSignal { layer: string; name: string; actual: string | null; meaning: string | null }
interface RagRange { horizon_bars: number | null; confidence: string; low: number | null; high: number | null }
interface RagSummary {
  stance?: string | null;
  signals?: RagSignal[];
  last_close?: number | null;
  price_ranges?: RagRange[];
  paragraph_data?: string | null;
  paragraph_implication?: string | null;
  bull_levels?: string[];
  bear_levels?: string[];
  catalysts?: string[];
  caveats?: string[];
  generated_at?: string | null;
}

const idr = (v: unknown) => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('en-US') : String(v);
};

const toneOf = (label?: string) =>
  (/pos|bull/i.test(label ?? '') ? 'bull' : /neg|bear/i.test(label ?? '') ? 'bear' : 'neutral') as 'bull' | 'bear' | 'neutral';

export const useAssessment = (ticker: string): Result<Assessment> => {
  const t = tk(ticker);
  const r = useApi<RagSummary>(`/rag/${t}/summary`);

  const data = useMemo<Assessment | null>(() => {
    const d = r.data;
    if (!d || !r.env) return null;

    const stance = d.stance?.trim();
    const summary = [d.paragraph_data, d.paragraph_implication].filter(Boolean).join(' ') || null;

    const ranges = (d.price_ranges ?? [])
      .filter((p) => p.low != null && p.high != null)
      .map((p) => `${p.confidence}${p.horizon_bars ? ` (${p.horizon_bars}d)` : ''}: ${idr(p.low)} to ${idr(p.high)}`);
    if (d.last_close != null) ranges.unshift(`Last close: ${idr(d.last_close)}`);

    const all: AssessmentBlock[] = [
      {
        heading: 'Signals', tone: 'neutral',
        items: (d.signals ?? []).map((s) =>
          `${[s.name, s.actual].filter(Boolean).join(': ')}${s.meaning ? ` — ${s.meaning}` : ''}`),
      },
      { heading: 'Price ranges', tone: 'neutral', items: ranges },
      { heading: 'Bull levels', tone: 'bull', items: (d.bull_levels ?? []).map(idr) },
      { heading: 'Bear levels', tone: 'bear', items: (d.bear_levels ?? []).map(idr) },
      { heading: 'Catalysts', tone: 'bull', items: d.catalysts ?? [] },
      { heading: 'Caveats', tone: 'neutral', items: (d.caveats ?? []).map((c) => human(c)) },
    ];

    return {
      ticker: t,
      verdict: stance ? { label: stance.charAt(0).toUpperCase() + stance.slice(1), tone: toneOf(stance) }
      : null,
      summary,
      blocks: all.filter((b) => b.items.length > 0),
      updatedAt: (d.generated_at ?? r.env.meta.fetched_at).slice(0, 10),
      author: 'AI analysis',
    };
  }, [r.data, r.env, t]);

  return { data, error: r.error, loading: r.loading };
};

// ---------- technical forecast -> forecast table ----------
interface Band { range_68?: number[]; range_95?: number[] }
interface Tech {
  last_close?: number;
  horizon_bars?: number;
  range_68pct?: number[];
  range_95pct?: number[];
  all_horizons?: Record<string, Band>;
  volatility?: { state?: string };
}

export const useForecast = (ticker: string): Result<Forecast> => {
  const t = tk(ticker);
  const { data: d, error } = useApi<Tech>(`/stocks/${t}/technical`);
  const data = useMemo<Forecast | null>(() => {
    if (!d) return null;
    const last = num(d.last_close);
    const hs: Array<[string, Band]> = d.all_horizons
      ? Object.entries(d.all_horizons).sort((a, b) => Number(a[0]) - Number(b[0]))
      : d.range_68pct ? [[String(d.horizon_bars ?? 5), { range_68: d.range_68pct, range_95: d.range_95pct }]] : [];
    if (last === null || hs.length === 0) return null;

    const periods: Forecast['periods'] = [{ label: 'Now', kind: 'actual' }, ...hs.map(([h]) => ({ label: `+${h}d`, kind: 'forecast' as const }))];
    const col = (f: (b: Band) => Num): Num[] => [last, ...hs.map(([, b]) => f(b))];
    const mid = (r?: number[]): Num => (r && r.length === 2 ? (r[0] + r[1]) / 2 : null);
    const edge = (r: number[] | undefined, i: 0 | 1): Num => num(r?.[i]);

    return {
      ticker: t,
      periods,
      rows: [
        { label: 'Central', unit: 'idr', values: col((b) => mid(b.range_68)), low: col((b) => edge(b.range_95, 0)).map((v, i) => (i === 0 ? null : v)), high: col((b) => edge(b.range_95, 1)).map((v, i) => (i === 0 ? null : v)) },
        { label: 'Bull Scenario', unit: 'idr', values: col((b) => edge(b.range_68, 1)) },
        { label: 'Bear Scenario', unit: 'idr', values: col((b) => edge(b.range_68, 0)) },
      ],
      note: `Price ranges in trading days. Range under Central is the 95% band${d.volatility?.state ? ` | volatility ${d.volatility.state}` : ''}`,
    };
  }, [d, t]);
  return { data, error };
};

// ---------- brokers -> ranking boards ----------
interface BrokerRow {
  broker_code: string; name: string | null;
  gross: number | null; net: number | null; foreign_net: number | null;   // raw IDR
}
interface BrokerPayload { date: string; ranking: BrokerRow[] }

const BOARDS: Record<string, {
  title: string; leadersLabel: string; moversLabel: string; moversChangeLabel: string;
  value: (r: BrokerRow) => Num; mover: (r: BrokerRow) => Num; moversAscending?: boolean;
}> = {
  gross:   { title: 'Broker trading value', leadersLabel: 'Largest by value', moversLabel: 'Net buyers', moversChangeLabel: 'Net buy', value: (r) => num(r.gross), mover: (r) => num(r.net) },
  foreign: { title: 'Foreign net buying', leadersLabel: 'Top foreign buyers', moversLabel: 'Top foreign sellers', moversChangeLabel: 'Net sell', value: (r) => num(r.foreign_net), mover: (r) => num(r.foreign_net), moversAscending: true },
  net:     { title: 'Net position', leadersLabel: 'Net buyers', moversLabel: 'Net sellers', moversChangeLabel: 'Net sell', value: (r) => num(r.net), mover: (r) => num(r.net), moversAscending: true },
};

// ---------- rankings: brokers / sectors / top stocks ----------
const BROKER_ALIAS: Record<string, keyof typeof BOARDS> = {
  brokers: 'gross', broker: 'gross', gross: 'gross', foreign: 'foreign', net: 'net',
};
const sum = (rows: RankRow[]) => rows.reduce((a, x) => a + (x.value ?? 0), 0);
const MONEY = 'idr'; // swap for 'idr' if you add one to lib/format

export const useRanking = (metric: string): Result<Leaderboard> => {
  const k = metric.trim().toLowerCase().replace(/\s+/g, '');      // "Top Stocks" -> "topstocks"
  const brokerKey = BROKER_ALIAS[k];
  const kind = brokerKey ? 'broker' : k === 'sectors' ? 'sectors' : k === 'topstocks' ? 'stocks' : null;

  const br = useApi<BrokerPayload>(kind === 'broker' ? '/brokers' : null);
  const co = useCompanyRows(kind === 'sectors' || kind === 'stocks');

  const data = useMemo<Leaderboard | null>(() => {
    // ---- brokers ----
    if (kind === 'broker') {
      const payload = br.data;
      const b = BOARDS[brokerKey];
      if (!payload || !Array.isArray(payload.ranking)) return null;
      const rows = payload.ranking;
      const label = (r: BrokerRow) => r.name ?? r.broker_code;
      const dir = b.moversAscending ? 1 : -1;   // 1 = sellers (most negative first), -1 = buyers (largest first)

      const leaders: RankRow[] = rows
        .filter((r) => (b.value(r) ?? 0) > 0)
        .sort((x, y) => (b.value(y) ?? 0) - (b.value(x) ?? 0))
        .slice(0, 10)
        .map((r) => ({ id: r.broker_code, name: label(r), value: b.value(r), change7d: null }));

      const movers: RankRow[] = rows
        .filter((r) => {
          const m = b.mover(r);
          if (m === null) return false;
          return b.moversAscending ? m < 0 : m > 0;   // sellers list only has sellers, buyers list only buyers
        })
        .sort((x, y) => dir * ((b.mover(x) as number) - (b.mover(y) as number)))
        .slice(0, 10)
        .map((r) => ({ id: r.broker_code, name: label(r), value: num(r.gross), change7d: b.mover(r) }));

      return {
          id: brokerKey, title: b.title, unit: 'idr', changeUnit: MONEY,
          headline: sum(leaders), headlineLabel: `Top 10 | ${payload.date}`,
          change30d: null, change90d: null, series: [],
          leadersLabel: b.leadersLabel, leaders, movers,
          moversLabel: b.moversLabel, moversChangeLabel: b.moversChangeLabel,
        };
    }

    // ---- sectors / top stocks (both from /companies) ----
    const all = co.data;
    if (!Array.isArray(all)) return null;
    


    // chg / chg_w arrive as ratios (-0.1486 = -14.86%). Use weekly if the backend sends it.
    const hasWeekly = all.some((r) => r.chg_w != null && r.chg_w !== r.chg);
    const chgOf = (r: CompanyRow) => ((hasWeekly ? (r.chg_w ?? r.chg) : r.chg) as number) * 100;
    const periodLabel = hasWeekly ? '7d change' : '1D change';
    const periodWord = hasWeekly ? 'this week' : 'today';

    if (kind === 'stocks') {
      const rows = all.filter((r) => r.market_cap !== null && r.chg !== null);
      if (rows.length === 0) return null;

      const leaders: RankRow[] = [...rows]
        .sort((a, b) => (b.market_cap as number) - (a.market_cap as number))
        .slice(0, 10)
        .map((r) => ({ id: tk(r.symbol), name: tk(r.symbol), value: r.market_cap, change7d: null }));

      const MIN_CAP = 1e12; // Rp 1T; raise or lower to taste

        const movers: RankRow[] = rows
          .filter((r) => (r.market_cap as number) >= MIN_CAP)
          .sort((a, b) => chgOf(b) - chgOf(a))
          .slice(0, 10)
          .map((r) => ({ id: tk(r.symbol), name: tk(r.symbol), value: r.market_cap, change7d: chgOf(r) }));

      return {
        id: 'topstocks', title: 'Top stocks', unit: MONEY, changeUnit: 'pct',
        headline: sum(leaders), headlineLabel: 'Top 10 by market cap',
        change30d: null, change90d: null, series: [],
        leadersLabel: 'Largest by market cap', leaders, movers,
        moversLabel: `Top gainers ${periodWord}`, moversChangeLabel: periodLabel,
      };
    }

    if (kind === 'sectors') {
      const rows = all.filter((r) => r.sub_sector && r.market_cap !== null && r.chg !== null);
      if (rows.length === 0) return null;

      const groups = new Map<string, CompanyRow[]>();
      rows.forEach((r) => groups.set(r.sub_sector as string, [...(groups.get(r.sub_sector as string) ?? []), r]));

      const agg = [...groups.entries()].map(([name, list]) => {
        const weight = list.reduce((a, r) => a + (r.market_cap as number), 0);
        const change = list.reduce((a, r) => a + chgOf(r), 0) / list.length;
        return { name, weight, change };
      });

      const leaders: RankRow[] = [...agg]
        .sort((a, b) => b.weight - a.weight).slice(0, 10)
        .map((x) => ({ id: x.name, name: x.name, value: x.weight, change7d: null }));

      const movers: RankRow[] = [...agg]
        .sort((a, b) => b.change - a.change).slice(0, 10)
        .map((x) => ({ id: x.name, name: x.name, value: x.weight, change7d: x.change }));

      return {
        id: 'sectors', title: 'Sectors', unit: MONEY, changeUnit: 'pct',
        headline: sum(leaders), headlineLabel: 'Top 10 sectors by market cap',
        change30d: null, change90d: null, series: [],
        leadersLabel: 'Largest sectors', leaders, movers,
        moversLabel: `Best sectors ${periodWord}`, moversChangeLabel: periodLabel,
      };
    }
    return null;
  }, [kind, brokerKey, br.data, co.data]);

  const error = kind === null ? `Unknown ranking "${metric}"` : (kind === 'broker' ? br.error : co.error);
  return { data, error };
};

// ---------- IHSG chart (no range tabs: the whole series the API returns) ----------
interface IhsgPayload {
  trend?: { trend?: string; slope_pct_per_bar?: number; degree?: number; normalize_slope?: number };
  series: { date: string; Close: number | null }[];
}

export const useIhsg = (): Result<PriceResponse> => {
  const { data: d, error } = useApi<IhsgPayload>('/market/ihsg/chart');
  const data = useMemo<PriceResponse | null>(() => {
    if (!d || !Array.isArray(d.series) || d.series.length === 0) return null;
    const points = d.series.map((r) => ({ t: String(r.date).slice(0, 10), v: num(r.Close) }));
    const first = points[0]?.v ?? null;
    const last = points[points.length - 1]?.v ?? null;
    return {
      symbol: 'IHSG', name: 'IHSG', currency: 'IDR',
      range: '5Y' as PriceRange, // placeholder to satisfy the type; PriceChart should hide the tabs for IHSG
      last, change: first && last ? (last / first - 1) * 100 : null, points,
    };
  }, [d]);
  return { data, error };
};

// Same URL as useIhsg, so SWR shares one request. Gives the "Strong Bear" style label.
export const useIhsgTrend = () => {
  const { data: d, error } = useApi<IhsgPayload>('/market/ihsg/chart');
  return { data: d?.trend ?? null, error };
};

