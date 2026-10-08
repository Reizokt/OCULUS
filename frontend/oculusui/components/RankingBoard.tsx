import { Delta, Empty, Panel, Sparkline } from './ui';
import { fmtSigned, fmtValue } from '../lib/format';
import type { Leaderboard } from '../types';

const SLOTS = 10;

export interface RankingBoardProps {
  /** null = no data yet (placeholder rows). */
  board: Leaderboard | null;
  /** Shown while board is null. */
  fallbackTitle?: string;
  error?: string | null;
  className?: string;
}

/** Leaderboard card: headline, sparkline, market leaders with bars, weekly movers. */
export function RankingBoard({ board, fallbackTitle = 'Ranking', error, className }: RankingBoardProps) {
  if (error) return <Panel className={className} title={fallbackTitle}><Empty>Could not load this ranking ({error}).</Empty></Panel>;

  const unit = board?.unit ?? 'idr';
  const leaders = board?.leaders ?? [];
  const movers = board?.movers ?? [];
  const max = Math.max(...leaders.map((l) => l.value ?? 0), 0);
  const maxMove = Math.max(...movers.map((m) => Math.abs(m.change7d ?? 0)), 0);

  return (
    <Panel
      className={className}
      title={board?.title ?? fallbackTitle}
      right={<div><div>30d: <Delta value={board?.change30d ?? null} /></div><div>90d: <Delta value={board?.change90d ?? null} /></div></div>}
    >
      <div className="mt-big">{fmtValue(board?.headline ?? null, unit)}</div>
      <div className="mt-muted">{board?.headlineLabel ?? 'Latest'}</div>
      <Sparkline values={board?.series ?? []} />

      <div className="mt-subhead"><span>{board?.leadersLabel ?? 'Market leaders'}</span><span>Latest</span></div>
      {Array.from({ length: SLOTS }, (_, i) => leaders[i] ?? null).map((row, i) => (
        <div className="mt-rank-row" key={row?.id ?? i}>
          <span className="mt-rank-name">{row?.name ?? '—'}</span>
          <div className="mt-bar-track">
            <div className={`mt-bar${row ? '' : ' ghost'}`} style={row && max > 0 ? { width: `${((row.value ?? 0) / max) * 100}%` } : undefined} />
          </div>
          <span className="mt-num">{fmtValue(row?.value ?? null, unit)}</span>
        </div>
      ))}

      <div className="mt-subhead"><span>{board?.moversLabel ?? 'Weekly movers'}</span><span>{board?.moversChangeLabel ?? '7d change'}</span></div>
      {Array.from({ length: SLOTS }, (_, i) => movers[i] ?? null).map((row, i) => (
        <div
          className="mt-mover"
          key={row?.id ?? i}
          style={{ borderImage: `linear-gradient(90deg,#4b6bf2 ${maxMove ? (Math.abs(row?.change7d ?? 0) / maxMove) * 100 : 0}%,#1b1b1b 0) 1` }}
        >
          <span className="mt-muted">{i + 1}</span>
          <span className="mt-rank-name">{row?.name ?? '—'}</span>
          <span className="mt-num">{fmtValue(row?.value ?? null, unit)}</span>
          <span className={`mt-num ${row?.change7d == null ? 'mt-flat' : row.change7d >= 0 ? 'mt-up' : 'mt-down'}`}>{fmtSigned(row?.change7d ?? null, board?.changeUnit ?? unit)}</span>
        </div>
      ))}
    </Panel>
  );
}
