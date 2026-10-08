'use client';

import { useMemo, type ReactNode } from 'react';
import { Treemap, type TreeGroup } from './Treemap';

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Decorative heatmap tiles. Not market data. */
export function makeBackdrop(seed = 11): TreeGroup[] {
  const r = mulberry32(seed);
  return Array.from({ length: 11 }, (_, g) => ({
    id: `g${g}`,
    label: '',
    weight: 1 + r() * 9,
    change: null,
    items: Array.from({ length: 6 + Math.floor(r() * 10) }, (_, i) => ({
      id: `g${g}-${i}`,
      label: '',
      weight: 0.2 + r() ** 2 * 6,
      change: (r() - 0.5) * 6,
    })),
  }));
}

export interface TerminalBackgroundProps {
  /** Centered content, e.g. a <SearchBox />. */
  children?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  /** Your own tiles (same shape as MiniMap groups). Defaults to a generated pattern. */
  tiles?: TreeGroup[];
  /** Pattern seed when `tiles` is not given. */
  seed?: number;
  minHeight?: number | string;
  /** Max width of the centered content. */
  contentWidth?: number | string;
  /** 0 to 1. How visible the heatmap is. */
  opacity?: number;
  /** Cancel the page padding so the background reaches the edges of `.mt-main`. */
  bleed?: boolean;
  className?: string;
}

/** Page or hero background: a faint sector heatmap behind centered content. */
export function TerminalBackground(props: TerminalBackgroundProps) {
  const { children, title, subtitle, tiles, seed = 11, minHeight = '64vh', contentWidth = 660, opacity = 0.5, bleed = false, className = '' } = props;
  const groups = useMemo(() => tiles ?? makeBackdrop(seed), [tiles, seed]);

  return (
    <div className={`mt-hero${bleed ? ' mt-bleed' : ''} ${className}`} style={{ minHeight }}>
      <div className="mt-hero-bg" aria-hidden="true" style={{ opacity }}>
        <Treemap groups={groups} showLabels={false} />
      </div>
      <div className="mt-hero-body" style={{ width: contentWidth }}>
        {title && <h1>{title}</h1>}
        {subtitle && <p>{subtitle}</p>}
        {children}
      </div>
    </div>
  );
}
