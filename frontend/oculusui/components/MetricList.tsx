import { Delta, Empty, Panel } from './ui';
import type { MetricGroup } from '../types';

export interface MetricListProps {
  groups: MetricGroup[] | null;
  error?: string | null;
  className?: string;
}

/** Sidebar of grouped metrics: label, value, % change. */
export function MetricList({ groups, error, className }: MetricListProps) {
  return (
    <Panel className={className}>
      {error ? (
        <Empty>Could not load metrics ({error}).</Empty>
      ) : (
        (groups ?? []).map((g) => (
          <div key={g.title}>
            <div className="mt-side-title">{g.title}</div>
            {g.rows.map((r) => (
              <div className="mt-metric" key={r.label}>
                <span>{r.label}</span>
                <span className="mt-metric-right"><span>{r.value ?? '—'}</span><Delta value={r.change} /></span>
              </div>
            ))}
          </div>
        ))
      )}
    </Panel>
  );
}
