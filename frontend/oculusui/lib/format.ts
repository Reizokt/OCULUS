import type { Unit } from '../types';

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 });

export function fmtValue(n: number | null, unit: Unit = 'usd'): string {
  if (n === null || Number.isNaN(n)) return '—';
  switch (unit) {
    case 'usd': return '$' + compact.format(n);
    case 'idr': return 'Rp\u00A0' + compact.format(n);
    case 'pct': return n.toFixed(1) + '%';
    case 'x': return n.toFixed(1) + 'x';
  }
  
  
}

export function fmtSigned(n: number | null, unit: Unit = 'pct'): string {
  if (n === null || Number.isNaN(n)) return '—';
  const sign = n > 0 ? '+' : n < 0 ? '-' : '';
  if (unit === 'pct') return sign + Math.abs(n).toFixed(1) + '%';
  return sign + fmtValue(Math.abs(n), unit);
}

export function fmtPct(n: number | null): string {
  if (n === null || Number.isNaN(n)) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
}

export function fmtShortDate(t: string): string {
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return t;
  const m = d.toLocaleString('en', { month: 'short', timeZone: 'UTC' });
  return `${m} '${String(d.getUTCFullYear()).slice(2)}`;
}

/** Heatmap colour for a % change. null → neutral grey. */
export function changeColor(c: number | null): string {
  if (c === null) return '#1b1b1b';
  const t = Math.min(Math.abs(c) / 3, 1);
  return c >= 0
    ? `hsl(152 ${40 + t * 20}% ${17 + t * 17}%)`
    : `hsl(2 ${45 + t * 20}% ${20 + t * 18}%)`;
}
