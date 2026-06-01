import { useEffect, useState } from 'react';

/** Tablet/touch: UI con Scatta foto anche se la larghezza supera 768px (es. tablet in landscape). */
export function matchCompactCaptureUI() {
  if (typeof window === 'undefined') return false;
  if (window.matchMedia('(max-width: 1024px)').matches) return true;
  if (window.matchMedia('(pointer: coarse)').matches) return true;
  if (navigator.maxTouchPoints > 0 && window.matchMedia('(hover: none)').matches) return true;
  return false;
}

export function useCompactCaptureUI() {
  const [compact, setCompact] = useState(() => matchCompactCaptureUI());

  useEffect(() => {
    const queries = [
      window.matchMedia('(max-width: 1024px)'),
      window.matchMedia('(pointer: coarse)'),
      window.matchMedia('(hover: none)'),
    ];
    const update = () => setCompact(matchCompactCaptureUI());
    queries.forEach((mq) => mq.addEventListener('change', update));
    window.addEventListener('resize', update);
    return () => {
      queries.forEach((mq) => mq.removeEventListener('change', update));
      window.removeEventListener('resize', update);
    };
  }, []);

  return compact;
}
