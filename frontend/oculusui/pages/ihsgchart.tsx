'use client';

import { PriceChartSection } from '../components/PriceChartSection';
import { useIhsg, useIhsgTrend } from '../data/hooks';

export function IhsgChart({ height, className }: { height?: number; className?: string }) {
  const { data, error } = useIhsg();
  const trend = useIhsgTrend();

  return (
    <PriceChartSection
      symbol="IHSG"
      name="IHSG"
      unit="idr"
      points={data?.points ?? null}
      last={data?.last ?? null}
      change={data?.change ?? null}
      error={error}
      height={height}
      className={className}
      toolbar={trend.data?.trend ? <span className="mt-pill">{trend.data.trend}</span> : undefined}
      /* no ranges / onRangeChange -> no 1M/3M/1Y/5Y tabs */
    />
  );
}