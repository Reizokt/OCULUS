import type { ReactNode } from 'react';
import { Empty, Panel } from './ui';
import type { Assessment } from '../types';

export interface NarrativeSectionProps {
  /** null = nothing written yet (empty state). */
  assessment: Assessment | null;
  title?: ReactNode;
  error?: string | null;
  loading?: boolean;          // new
  className?: string;
}

/** Written assessment: verdict chip, summary paragraph, then Thesis / Risks / Catalysts style blocks. */
export function NarrativeSection({ assessment, title = 'Assessment', error, loading,className }: NarrativeSectionProps) {
  const a = assessment;
  const meta = a?.updatedAt ? `Updated ${a.updatedAt}${a.author ? ` by ${a.author}` : ''}` : undefined;

  return (
    <Panel
      className={className}
      title={title}
      subtitle={meta}
      right={a?.verdict ? <span className={`mt-verdict mt-tone-${a.verdict.tone}`}>{a.verdict.label}</span> : undefined}
    >
      {error ? (
    <Empty>Could not load the assessment ({error}).</Empty>
      ) : loading ? (
        <Empty>Generating assessment… the first run for a ticker can take a minute.</Empty>
      ) : (
    <> {a?.summary
            ? <p className="mt-summary">{a.summary}</p>
            : <p className="mt-summary mt-muted">No assessment has been written yet.</p>}
          {(a?.blocks.length ?? 0) > 0 && (
            <div className="mt-blocks">
              {a!.blocks.map((b) => (
                <div className={`mt-block mt-tone-${b.tone}`} key={b.heading}>
                  <div className="mt-block-head">{b.heading}</div>
                  {b.items.length > 0
                    ? <ul>{b.items.map((it) => <li key={it}>{it}</li>)}</ul>
                    : <div className="mt-muted">Nothing added yet.</div>}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
