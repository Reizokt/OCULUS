'use client';

import type { ReactNode } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Chip, Empty, Panel } from './ui';
import { fmtShortDate, fmtValue } from '../lib/format';
import type { Num, PricePoint, PriceRange } from '../types';

const AXIS = { fill: '#8d8d8d', fontSize: 12 };

export interface PriceChartSectionProps {
  symbol: string;
  /** Display name. Defaults to the symbol. */
  name?: string;
  /** null = no data yet (empty state). */
  points: PricePoint[] | null;
  last?: Num;
  /** % change over the shown range. */
  change?: Num;
  /** Show range tabs: pass all three. */
  ranges?: PriceRange[];
  range?: PriceRange;
  onRangeChange?: (range: PriceRange) => void;
  /** Extra controls on the right of the header (e.g. symbol pills). */
  toolbar?: ReactNode;
  height?: number;
  error?: string | null;
  className?: string;
  // in PriceChartSectionProps
  unit?: Parameters<typeof fmtValue>[1];
}

/** Line chart section with headline price, % change chip and optional range tabs. */
export function PriceChartSection(props: PriceChartSectionProps) {
  const { symbol, name, points, last = null, change = null, ranges, range, onRangeChange, toolbar, height = 320, error, className, unit = 'idr' } = props;
  const hasData = (points ?? []).some((p) => p.v !== null);

  return (
    <Panel
      className={className}
      title={<>{name ?? symbol} price <span className="mt-muted">{fmtValue(last, unit)}</span> <Chip value={change} /></>}
      subtitle={range ? `${symbol} | ${range}` : symbol}
      right={
        <>
          {toolbar}
          {ranges && onRangeChange && (
            <div className="mt-tabs" role="group" aria-label="Range">
              {ranges.map((r) => (
                <button key={r} aria-pressed={r === range} onClick={() => onRangeChange(r)}>{r}</button>
              ))}
            </div>
          )}
        </>
      }
    >
      {error ? (
        <Empty>Could not load prices ({error}).</Empty>
      ) : !hasData ? (
        <Empty>No price data yet for {symbol}.</Empty>
      ) : (
        <div className="mt-chart" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#1e1e1e" vertical={false} />
              <XAxis dataKey="t" tickFormatter={fmtShortDate} tick={AXIS} axisLine={false} tickLine={false} minTickGap={56} />
              <YAxis tickFormatter={(v: number) => fmtValue(v, 'idr')} tick={AXIS} axisLine={false} tickLine={false} width={52} domain={['auto', 'auto']} />
              <Tooltip
    content={({ active, payload, label }) => {
      if (!active || !payload?.length) return null;
      const v = payload[0]?.payload?.v;                       // value of the hovered point
      const formatted = typeof v === 'number' ? fmtValue(v, unit) : null;
      const text =
        formatted && formatted !== '—' ? formatted
        : typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 })
        : '—';
      return (
        <div style={{ background: '#161616', border: '1px solid #2a2a2a', borderRadius: 8, padding: '8px 12px' }}>
          <div style={{ color: '#8d8d8d' }}>{label}</div>
          <div style={{ color: '#fff', fontWeight: 600 }}>{text}</div>
        </div>
      );
    }}
  />
              <Line type="monotone" dataKey="v" stroke="#19ffa8" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
