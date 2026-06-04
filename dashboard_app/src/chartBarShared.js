import { useEffect, useState } from 'react';

export const BAR_CHART_W = 640;
export const BAR_CHART_H = 220;
export const BAR_PAD = { top: 28, right: 12, bottom: 36, left: 48 };
export const BAR_PAD_MOBILE = { top: 32, right: 8, bottom: 42, left: 56 };

export function useMobileChartLayout() {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 768px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const onChange = (e) => setMobile(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return mobile;
}

export function chartFontSizes(mobile) {
  if (mobile) {
    return { axisY: 14, axisX: 12, value: 13, compact: 11 };
  }
  return { axisY: 11, axisX: 10, value: 11, compact: 9 };
}

export function formatEuroAxis(n) {
  if (n >= 1000) return `€${(n / 1000).toFixed(1)}k`;
  return `€${Math.round(n)}`;
}

export function formatBarValue(n) {
  const v = Number(n) || 0;
  if (v >= 10000) return `€${Math.round(v / 1000)}k`;
  if (v >= 1000) return `€${(v / 1000).toFixed(1).replace('.', ',')}k`;
  return `€${Math.round(v).toLocaleString('it-IT')}`;
}
