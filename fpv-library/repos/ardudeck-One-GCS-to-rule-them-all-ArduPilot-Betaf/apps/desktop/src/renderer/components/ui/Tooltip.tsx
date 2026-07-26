import React, { useCallback, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

type Placement = 'top' | 'bottom' | 'left' | 'right';

interface TooltipProps {
  content: React.ReactNode;
  placement?: Placement;
  children: React.ReactElement;
  className?: string;
  // Set false when content needs to wrap (e.g. long descriptions).
  nowrap?: boolean;
}

const OFFSET = 6; // px gap between target and tooltip

// Zero-delay tooltip portalled to document.body so it escapes stacking contexts
// created by parent transforms (virtualized rows, etc.).
export function Tooltip({ content, placement = 'top', children, className = '', nowrap = true }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [style, setStyle] = useState<React.CSSProperties>({});
  const wrapRef = useRef<HTMLSpanElement>(null);

  const show = useCallback(() => {
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const next: React.CSSProperties = { position: 'fixed', zIndex: 100 };
    switch (placement) {
      case 'top':
        next.bottom = window.innerHeight - rect.top + OFFSET;
        next.left = rect.left + rect.width / 2;
        next.transform = 'translateX(-50%)';
        break;
      case 'bottom':
        next.top = rect.bottom + OFFSET;
        next.left = rect.left + rect.width / 2;
        next.transform = 'translateX(-50%)';
        break;
      case 'left':
        next.right = window.innerWidth - rect.left + OFFSET;
        next.top = rect.top + rect.height / 2;
        next.transform = 'translateY(-50%)';
        break;
      case 'right':
        next.left = rect.right + OFFSET;
        next.top = rect.top + rect.height / 2;
        next.transform = 'translateY(-50%)';
        break;
    }
    setStyle(next);
    setVisible(true);
  }, [placement]);

  const hide = useCallback(() => setVisible(false), []);

  return (
    <span
      ref={wrapRef}
      className="relative inline-flex min-w-0 max-w-full"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible &&
        createPortal(
          <span
            role="tooltip"
            style={style}
            className={`pointer-events-none px-2 py-1 bg-surface-solid border border-subtle text-content text-xs rounded shadow-lg ${nowrap ? 'whitespace-nowrap' : ''} ${className}`}
          >
            {content}
          </span>,
          document.body,
        )}
    </span>
  );
}
