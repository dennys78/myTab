import { useMemo, useState } from 'react';
import { STORICO_PERIOD_OPTIONS } from './dateFilters';
import { getFilteredClosureSeries, isGrattaEVinci, isTabacchi } from './repartiChartUtils';

const CHART_W = 400;
const CHART_H = 160;
const PAD = { top: 12, right: 12, bottom: 28, left: 44 };

function formatShortDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
}

function formatEuro(n) {
  if (n >= 1000) return `€${(n / 1000).toFixed(1)}k`;
  return `€${Math.round(n)}`;
}

function MiniLineChart({ title, subtitle, color, series }) {
  const plotW = CHART_W - PAD.left - PAD.right;
  const plotH = CHART_H - PAD.top - PAD.bottom;

  const chart = useMemo(() => {
    if (!series.length) {
      return { path: '', areaPath: '', points: [], yTicks: [0], xLabels: [], minVal: 0, maxVal: 1, range: 1 };
    }

    const values = series.map((p) => p.value);
    const maxVal = Math.max(...values, 1);
    const minVal = Math.min(0, ...values);
    const range = maxVal - minVal || 1;

    const pts = series.map((p, i) => {
      const x = PAD.left + (series.length === 1 ? plotW / 2 : (i / (series.length - 1)) * plotW);
      const y = PAD.top + plotH - ((p.value - minVal) / range) * plotH;
      return { x, y, ...p };
    });

    const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const area = `${linePath} L ${pts[pts.length - 1].x.toFixed(1)} ${(PAD.top + plotH).toFixed(1)} L ${pts[0].x.toFixed(1)} ${(PAD.top + plotH).toFixed(1)} Z`;

    const ticks = [minVal, minVal + range * 0.5, maxVal];
    const labels = series.length <= 6
      ? series.map((p) => formatShortDate(p.date))
      : [series[0], series[Math.floor(series.length / 2)], series[series.length - 1]].map((p) => formatShortDate(p.date));

    return {
      path: linePath,
      areaPath: area,
      points: pts,
      yTicks: ticks,
      xLabels: labels,
      minVal,
      maxVal,
      range,
    };
  }, [series, plotW, plotH]);

  if (!series.length) {
    return (
      <article className="reparti-chart-card">
        <header className="reparti-chart-card__head">
          <h3 className="reparti-chart-card__title" style={{ color }}>{title}</h3>
          <p className="reparti-chart-card__sub">{subtitle}</p>
        </header>
        <div className="reparti-chart-empty">Nessun dato nel periodo selezionato.</div>
      </article>
    );
  }

  const { path, areaPath, points, yTicks, xLabels, minVal, range } = chart;

  return (
    <article className="reparti-chart-card">
      <header className="reparti-chart-card__head">
        <h3 className="reparti-chart-card__title" style={{ color }}>{title}</h3>
        <p className="reparti-chart-card__sub">{subtitle}</p>
        <div className="reparti-chart-card__total" style={{ color }}>
          Ultimo: € {series[series.length - 1].value.toFixed(2)}
        </div>
      </header>
      <svg
        className="reparti-chart-svg"
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        role="img"
        aria-label={`${title}: andamento saldo per giorno`}
      >
        {yTicks.map((tick, i) => {
          const y = PAD.top + plotH - ((tick - minVal) / range) * plotH;
          return (
            <g key={tick}>
              <line x1={PAD.left} y1={y} x2={CHART_W - PAD.right} y2={y} className="reparti-chart-grid" />
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" className="reparti-chart-axis">
                {formatEuro(tick)}
              </text>
            </g>
          );
        })}
        <path d={areaPath} fill={color} fillOpacity="0.12" />
        <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p) => (
          <circle key={p.date} cx={p.x} cy={p.y} r="3.5" fill={color} stroke="var(--bg-card)" strokeWidth="1.5">
            <title>{`${formatShortDate(p.date)}: € ${p.value.toFixed(2)}`}</title>
          </circle>
        ))}
        {xLabels.map((label, i) => {
          const x = PAD.left + (xLabels.length === 1 ? plotW / 2 : (i / (xLabels.length - 1)) * plotW);
          return (
            <text key={label + i} x={x} y={CHART_H - 6} textAnchor="middle" className="reparti-chart-axis">
              {label}
            </text>
          );
        })}
      </svg>
    </article>
  );
}

export default function RepartiTrendCharts({ closures }) {
  const [period, setPeriod] = useState('month');

  const tabacchiSeries = useMemo(
    () => getFilteredClosureSeries(closures, period, isTabacchi),
    [closures, period],
  );
  const grattaSeries = useMemo(
    () => getFilteredClosureSeries(closures, period, isGrattaEVinci),
    [closures, period],
  );

  return (
    <section className="reparti-charts-section" aria-labelledby="reparti-charts-heading">
      <div className="reparti-charts-section__header">
        <div>
          <h2 id="reparti-charts-heading" className="reparti-charts-section__title">Andamento reparti</h2>
          <p className="reparti-charts-section__hint">Saldo giornaliero da chiusure cassa (Tabacchi e Gratta e Vinci).</p>
        </div>
        <div className="reparti-charts-section__filter">
          <label htmlFor="reparti-chart-period" className="reparti-charts-section__filter-label">Periodo</label>
          <select
            id="reparti-chart-period"
            className="storico-period-select"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            {STORICO_PERIOD_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="reparti-charts-grid">
        <MiniLineChart
          title="Tabacchi"
          subtitle="Saldo cassa per giorno"
          color="#d97706"
          series={tabacchiSeries}
        />
        <MiniLineChart
          title="Gratta e Vinci"
          subtitle="Saldo cassa per giorno"
          color="#8b5cf6"
          series={grattaSeries}
        />
      </div>
    </section>
  );
}
