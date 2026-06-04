import { useMemo } from 'react';
import {
  BAR_CHART_H,
  BAR_CHART_W,
  BAR_PAD,
  BAR_PAD_MOBILE,
  chartFontSizes,
  formatBarValue,
  formatEuroAxis,
  useMobileChartLayout,
} from './chartBarShared';

export default function BarColumnChart({
  series,
  chartW = BAR_CHART_W,
  chartH = BAR_CHART_H,
  barColor = '#22c55e',
  barMutedOpacity = 0.55,
  highlightIndex = null,
  ariaLabel = 'Grafico a colonne',
  svgClassName = 'bar-column-chart-svg',
  emptyClassName = 'bar-column-chart-empty',
  maxXLabels = 12,
}) {
  const mobile = useMobileChartLayout();
  const pad = mobile ? BAR_PAD_MOBILE : BAR_PAD;
  const fs = chartFontSizes(mobile);
  const plotW = chartW - pad.left - pad.right;
  const plotH = chartH - pad.top - pad.bottom;

  const chart = useMemo(() => {
    if (!series.length) return null;
    const maxVal = Math.max(...series.map((p) => p.value), 1);
    const barGap = 4;
    const barW = Math.max(4, (plotW - barGap * (series.length - 1)) / series.length);

    const bars = series.map((p, i) => {
      const h = p.value > 0 ? (p.value / maxVal) * plotH : 0;
      const x = pad.left + i * (barW + barGap);
      const y = pad.top + plotH - h;
      return { ...p, x, y, w: barW, h, i };
    });

    const yTicks = [0, maxVal * 0.5, maxVal];
    return { bars, maxVal, yTicks };
  }, [series, plotW, plotH, pad.left, pad.top]);

  if (!chart) {
    return (
      <div className={emptyClassName}>Nessun dato nel periodo selezionato.</div>
    );
  }

  const { bars, maxVal, yTicks } = chart;
  const xLabelStride = series.length <= maxXLabels
    ? 1
    : Math.ceil(series.length / maxXLabels);

  return (
    <svg
      className={svgClassName}
      viewBox={`0 0 ${chartW} ${chartH}`}
      role="img"
      aria-label={ariaLabel}
    >
      {yTicks.map((tick) => {
        const y = pad.top + plotH - (tick / maxVal) * plotH;
        return (
          <g key={tick}>
            <line x1={pad.left} y1={y} x2={chartW - pad.right} y2={y} className="bar-column-chart-grid" />
            <text
              x={pad.left - 8}
              y={y + 4}
              textAnchor="end"
              className="bar-column-chart-axis"
              fontSize={fs.axisY}
            >
              {formatEuroAxis(tick)}
            </text>
          </g>
        );
      })}
      {bars.map((b) => {
        const isHighlight = highlightIndex != null && b.i === highlightIndex;
        const showValue = b.value > 0 && b.w >= 10;
        const label = formatBarValue(b.value);
        const labelInside = showValue && b.h >= (mobile ? 26 : 22);
        const labelY = labelInside ? b.y + (mobile ? 16 : 14) : Math.max(pad.top + 10, b.y - 6);
        const compact = b.w < (mobile ? 22 : 18);
        const valueClass = [
          'bar-column-chart-value',
          isHighlight ? 'bar-column-chart-value--highlight' : '',
          labelInside ? 'bar-column-chart-value--inside' : '',
          compact ? 'bar-column-chart-value--compact' : '',
        ].filter(Boolean).join(' ');

        return (
          <g key={`${b.label}-${b.i}`}>
            {b.h > 0 && (
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={3}
                fill={barColor}
                fillOpacity={isHighlight ? 1 : barMutedOpacity}
              >
                <title>{`${b.label}: € ${b.value.toFixed(2)}`}</title>
              </rect>
            )}
            {showValue && (
              <text
                x={b.x + b.w / 2}
                y={labelY}
                textAnchor="middle"
                className={valueClass}
                fontSize={compact ? fs.compact : fs.value}
              >
                {label}
              </text>
            )}
            {(series.length <= maxXLabels
              || b.i % xLabelStride === 0
              || b.i === series.length - 1) && (
              <text
                x={b.x + b.w / 2}
                y={chartH - (mobile ? 10 : 8)}
                textAnchor="middle"
                className="bar-column-chart-axis bar-column-chart-axis--x"
                fontSize={fs.axisX}
              >
                {b.label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
