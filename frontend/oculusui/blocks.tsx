'use client';

// "Blocks" = a component + the hook that feeds it. Pages only use blocks,
// so adding a card to a page is a single line, e.g. <Forecast ticker={ticker} />.
import { useState, type ReactNode } from 'react';
import { ForecastTable } from './components/ForecastTable';
import { MetricList } from './components/MetricList';
import { MiniMap, sectorsToGroups } from './components/MiniMap';
import { NarrativeSection } from './components/NarrativeSection';
import { PriceChartSection } from './components/PriceChartSection';
import { RankingBoard } from './components/RankingBoard';
import { useAssessment, useCompany, useForecast, usePrices, useRanking, useSectors } from './data/hooks';
import type { PriceRange } from './types';

const RANGES: PriceRange[] = ['1M', '3M', '1Y', '5Y'];

export function PriceChart({ symbol, toolbar }: { symbol: string; toolbar?: ReactNode }) {
  const [range, setRange] = useState<PriceRange>('1Y');
  const { data, error } = usePrices(symbol, range);
  return (
    <PriceChartSection
      symbol={symbol} name={data?.name} points={data?.points ?? null} last={data?.last} change={data?.change}
      ranges={RANGES} range={range} onRangeChange={setRange} toolbar={toolbar} error={error}
    />
  );
}

export function Assessment({ ticker }: { ticker: string }) {
  const { data, error, loading } = useAssessment(ticker);
  return <NarrativeSection assessment={data} error={error} loading={loading} />;
}

export function Forecast({ ticker }: { ticker: string }) {
  const { data, error } = useForecast(ticker);
  return <ForecastTable forecast={data} error={error} />;
}

export function SectorMap(props: { size?: 'mini' | 'full'; onSelect?: (symbol: string) => void; action?: ReactNode; title?: string }) {
  const { data, error } = useSectors();
  return (
    <MiniMap
      title={props.title ?? 'Sector growth'} subtitle={`Size by market weight | change over ${data?.period ?? '1D'}`}
      groups={sectorsToGroups(data)} size={props.size} onSelect={props.onSelect} action={props.action} error={error}
    />
  );
}

export function Ranking({ metric }: { metric: string }) {
  const { data, error } = useRanking(metric);
  return <RankingBoard board={data} fallbackTitle={metric} error={error} />;
}

export function Metrics({ ticker }: { ticker: string }) {
  const { data, error } = useCompany(ticker);
  return <MetricList groups={data?.metricGroups ?? null} error={error} />;
}
