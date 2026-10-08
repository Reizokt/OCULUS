import type { ReactNode } from 'react';
import { fmtPct } from '../lib/format';

/** The base card. Everything on every page is a Panel inside a grid cell. */
export function Panel(props: {
  title?: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  const { title, subtitle, right, className = '', children } = props;
  return (
    <div className={`mt-panel ${className}`}>
      {(title || right) && (
        <div className="mt-panel-head">
          <div>
            <div className="mt-panel-title">{title}</div>
            {subtitle && <div className="mt-panel-sub">{subtitle}</div>}
          </div>
          {right && <div className="mt-panel-right">{right}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

export function Delta({ value }: { value: number | null }) {
  const cls = value === null ? 'mt-flat' : value >= 0 ? 'mt-up' : 'mt-down';
  return <span className={cls}>{fmtPct(value)}</span>;
}

export function Chip({ value }: { value: number | null }) {
  if (value === null) return null;
  const cls = value >= 0 ? 'mt-up' : 'mt-down';
  return <span className={`mt-chip ${cls}`}>{value >= 0 ? '↑' : '↓'} {Math.abs(value).toFixed(1)}%</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="mt-empty">{children}</div>;
}

export function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="mt-spark mt-spark-empty" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${28 - ((v - min) / span) * 26}`);
  return (
    <svg className="mt-spark" viewBox="0 0 100 30" preserveAspectRatio="none">
      <polygon points={`0,30 ${pts.join(' ')} 100,30`} fill="#19ffa8" opacity=".12" />
      <polyline points={pts.join(' ')} fill="none" stroke="#19ffa8" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
