'use client';

import { useEffect, useState, type KeyboardEvent } from 'react';
import type { SearchResult } from '../types';

export interface SearchBoxProps {
  /** Suggestions to show. You fetch them; the box only displays them. */
  results: SearchResult[];
  /** Called (debounced) when the text changes. Use it to fetch `results`. */
  onQueryChange: (query: string) => void;
  /** Called with an upper-case ticker when the user picks a result or presses Enter. */
  onSelect: (ticker: string) => void;
  placeholder?: string;
  debounceMs?: number;
  autoFocus?: boolean;
  className?: string;
}

export function SearchBox(props: SearchBoxProps) {
  const { results, onQueryChange, onSelect, placeholder = 'Search companies, e.g. ACME', debounceMs = 200, autoFocus = false, className = '' } = props;
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => onQueryChange(q.trim()), debounceMs);
    return () => clearTimeout(t);
  }, [q, debounceMs, onQueryChange]);

  const shown = q.trim() ? results : [];
  const go = (ticker: string) => onSelect(ticker.trim().toUpperCase());

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, shown.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') {
      if (shown[active]) go(shown[active].ticker);
      else if (q.trim()) go(q);
    }
  };

  return (
    <div className={`mt-search ${className}`}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setActive(0); }}
        onKeyDown={onKey}
        placeholder={placeholder}
        aria-label="Search companies"
        autoFocus={autoFocus}
      />
      {shown.length > 0 && (
        <div className="mt-suggest" role="listbox">
          {shown.map((r, i) => (
            <button key={r.ticker} role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(r.ticker)}>
              <span>{r.name} <small>{r.sector ?? ''}</small></span>
              <span className="mt-muted">{r.ticker}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
