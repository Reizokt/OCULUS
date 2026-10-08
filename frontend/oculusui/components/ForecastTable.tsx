import type { ReactNode } from 'react';
import { Delta, Empty, Panel } from './ui';
import { fmtValue } from '../lib/format';
import type { Forecast } from '../types';

export interface ForecastTableProps {
  /** null = no forecast yet (empty state). */
  forecast: Forecast | null;
  title?: ReactNode;
  /** Show the low to high analyst range under forecast values. */
  showRange?: boolean;
  /** Show year-over-year change under each value. */
  showGrowth?: boolean;
  error?: string | null;
  className?: string;
}

/** Metrics by period. Actual columns are plain, forecast columns are tinted and can show a range. */
export function ForecastTable({ forecast, title = 'Forecast', showRange = true, showGrowth = true, error, className }: ForecastTableProps) {
  const periods = forecast?.periods ?? [];
  const rows = forecast?.rows ?? [];

  return (
    <Panel
      className={className}
      title={title}
      subtitle={forecast?.note ?? undefined}
      right={<div className="mt-key"><span><i className="mt-key-actual" />Actual</span><span><i className="mt-key-est" />Estimate</span></div>}
    >
      {error ? (
        <Empty>Could not load the forecast ({error}).</Empty>
      ) : periods.length === 0 ? (
        <Empty>No forecast yet.</Empty>
      ) : (
        <div className="mt-table-wrap">
          <table className="mt-table">
            <thead>
              <tr>
                <th />
                {periods.map((p) => <th key={p.label} className={`is-${p.kind}`}>{p.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  {periods.map((p, i) => {
                    const v = row.values[i] ?? null;
                    const base = row.values[0] ?? null;
                    const growth = showGrowth && i > 0 && v !== null && base !== null && base !== 0 && (row.unit === 'usd' || row.unit === 'idr')
                    ? (v / base - 1) * 100 : null;
                    const lo = row.low?.[i] ?? null;
                    const hi = row.high?.[i] ?? null;
                    return (
                      <td key={p.label} className={`is-${p.kind}`}>
                        <div>{fmtValue(v, row.unit)}</div>
                        {growth !== null && <small><Delta value={growth} /></small>}
                        {showRange && p.kind === 'forecast' && lo !== null && hi !== null && (
                          <small className="mt-muted">{fmtValue(lo, row.unit)} to {fmtValue(hi, row.unit)}</small>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
