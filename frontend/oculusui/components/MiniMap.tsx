'use client';

import type { ReactNode } from 'react';
import { Empty, Panel } from './ui';
import { Treemap, type TreeGroup } from './Treemap';
import type { SectorsResponse } from '../types';

/** Adapter: sector payload to the groups MiniMap draws. */
export function sectorsToGroups(res: SectorsResponse | null): TreeGroup[] {
  return (res?.sectors ?? []).map((s) => ({
    id: s.id,
    label: s.name,
    weight: s.weight,
    change: s.change,
    items: s.stocks.map((st) => ({ id: st.symbol, label: st.symbol, weight: st.weight, change: st.change })),
  }));
}

export interface MiniMapProps {
  /** null or [] = no data yet (empty state). */
  groups: TreeGroup[] | null;
  title?: ReactNode;
  subtitle?: ReactNode;
  /** 'mini' is a compact card, 'full' fills a 16:10 area with sector headers. */
  size?: 'mini' | 'full';
  /** Pixel height for 'mini'. */
  height?: number;
  /** Sector header strips. Default: on for 'full', off for 'mini'. */
  groupLabels?: boolean;
  showScale?: boolean;
  /** Called with the tile id (stock symbol) when a tile is clicked. */
  onSelect?: (id: string) => void;
  /** Right side of the header, e.g. a link to the full map. */
  action?: ReactNode;
  error?: string | null;
  className?: string;
}

/** Heatmap of sectors and stocks. Area = weight, colour = % change. */
export function MiniMap(props: MiniMapProps) {
  const { groups, title = 'Sector map', subtitle, size = 'mini', height = 240, groupLabels, showScale = size === 'full', onSelect, action, error, className } = props;
  const empty = !groups || groups.length === 0;

  return (
    <Panel
      className={className}
      title={title}
      subtitle={subtitle}
      right={<>{showScale && <div className="mt-scale"><span>-3%</span><i /><span>+3%</span></div>}{action}</>}
    >
      {error ? (
        <Empty>Could not load the map ({error}).</Empty>
      ) : empty ? (
        <Empty>No map data yet.</Empty>
      ) : (
        <div className={size === 'full' ? 'mt-map-wrap' : 'mt-map-mini'} style={size === 'mini' ? { height } : undefined}>
          <Treemap groups={groups} groupLabels={groupLabels ?? size === 'full'} onItemClick={onSelect} />
        </div>
      )}
    </Panel>
  );
}
