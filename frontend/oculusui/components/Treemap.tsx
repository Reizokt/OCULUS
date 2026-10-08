'use client';

import type { CSSProperties } from 'react';
import { changeColor, fmtPct } from '../lib/format';

export interface Rect { x: number; y: number; w: number; h: number }

/** Squarified treemap. `weights` must be > 0 and sorted descending. */
export function squarify(weights: number[], box: Rect): Rect[] {
  const total = weights.reduce((a, b) => a + b, 0);
  if (total <= 0 || weights.length === 0) return [];
  const area = box.w * box.h;
  const scaled = weights.map((w) => (w / total) * area);
  const out: Rect[] = new Array(weights.length);
  let { x, y, w, h } = box;

  const worst = (row: number[], side: number) => {
    const s = row.reduce((a, b) => a + b, 0);
    const mx = Math.max(...row);
    const mn = Math.min(...row);
    return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
  };

  let i = 0;
  while (i < scaled.length) {
    const side = Math.min(w, h);
    let row = [scaled[i]];
    let j = i + 1;
    while (j < scaled.length) {
      const next = [...row, scaled[j]];
      if (worst(next, side) <= worst(row, side)) { row = next; j++; } else break;
    }
    const rowSum = row.reduce((a, b) => a + b, 0);
    if (w >= h) {
      const cw = rowSum / h;
      let cy = y;
      row.forEach((a, k) => { const rh = a / cw; out[i + k] = { x, y: cy, w: cw, h: rh }; cy += rh; });
      x += cw; w -= cw;
    } else {
      const rh = rowSum / w;
      let cx = x;
      row.forEach((a, k) => { const rw = a / rh; out[i + k] = { x: cx, y, w: rw, h: rh }; cx += rw; });
      y += rh; h -= rh;
    }
    i = j;
  }
  return out;
}


export interface TreeItem { id: string; label: string; weight: number | null; change: number | null }
export interface TreeGroup extends TreeItem { items: TreeItem[] }

const W = 160;
const H = 100;

function weights(items: { weight: number | null }[]): number[] {
  const pos = items.map((i) => i.weight).filter((w): w is number => w !== null && w > 0);
  const fallback = pos.length ? Math.min(...pos) : 1;
  return items.map((i) => (i.weight !== null && i.weight > 0 ? i.weight : fallback));
}

function place<T extends { weight: number | null }>(items: T[], box: Rect) {
  const w = weights(items);
  const order = items.map((_, i) => i).sort((a, b) => w[b] - w[a]);
  const rects = squarify(order.map((i) => w[i]), box);
  return order.map((idx, k) => ({ item: items[idx], rect: rects[k] }));
}

function pos(r: Rect, w: number, h: number): CSSProperties {
  return { left: `${(r.x / w) * 100}%`, top: `${(r.y / h) * 100}%`, width: `${(r.w / w) * 100}%`, height: `${(r.h / h) * 100}%` };
}

export function Treemap(props: {
  groups: TreeGroup[];
  /** tile labels (symbol + %) */
  showLabels?: boolean;
  /** group header strip; defaults to showLabels */
  groupLabels?: boolean;
  onItemClick?: (id: string) => void;
  className?: string;
}) {
  const { groups, showLabels = true, groupLabels = showLabels, onItemClick, className = '' } = props;
  const placed = place(groups, { x: 0, y: 0, w: W, h: H });

  return (
    <div className={`mt-treemap ${className}`}>
      {placed.map(({ item: g, rect: r }) => {
        const inner = place(g.items, { x: 0, y: 0, w: r.w, h: r.h });
        return (
          <div className="mt-tm-group" key={g.id} style={pos(r, W, H)}>
            {groupLabels && (
              <div className="mt-tm-grouplabel">
                <span>{g.label}</span>
                <span>{fmtPct(g.change)}</span>
              </div>
            )}
            <div className={`mt-tm-items${groupLabels ? ' has-label' : ''}`}>
              {g.items.length === 0 && (
                <div className="mt-tile" style={{ inset: 0, background: changeColor(g.change) }} />
              )}
              {inner.map(({ item: it, rect: ir }) => (
                <div
                  key={it.id}
                  className="mt-tile"
                  role={onItemClick ? 'button' : undefined}
                  tabIndex={onItemClick ? 0 : undefined}
                  onClick={onItemClick ? () => onItemClick(it.id) : undefined}
                  onKeyDown={onItemClick ? (e) => { if (e.key === 'Enter') onItemClick(it.id); } : undefined}
                  style={{ ...pos(ir, r.w, r.h), background: changeColor(it.change), cursor: onItemClick ? 'pointer' : 'default' }}
                >
                  {showLabels && (<><b>{it.label}</b><span>{fmtPct(it.change)}</span></>)}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
