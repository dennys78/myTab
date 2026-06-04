import { useEffect, useMemo, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { useAuth } from './auth';
import { loadUserPreference, saveUserPreference } from './userPreferences';
import { collectDepartmentsFromClosures } from './repartiChartUtils';
import {
  INCASSATO_PERIOD_OPTIONS,
  INCASSATO_SCOPE_ALL,
  averageNonZeroValues,
  getCurrentMonthName,
  getDailyIncassatoSeries,
  getMonthlyIncassatoSeries,
  getTotalIncassatoForMonth,
  getTotalIncassatoForYear,
} from './incassatoUtils';

const PREF_INCASSATO_PERIOD = 'incassatoDashboardPeriod';
const PREF_INCASSATO_SCOPE = 'incassatoDashboardScope';
const PERIOD_VALUES = INCASSATO_PERIOD_OPTIONS.map((o) => o.value);
const DEFAULT_PERIOD = 'month';

const CHART_W = 640;
const CHART_H = 220;
const PAD = { top: 28, right: 12, bottom: 36, left: 48 };
const PAD_MOBILE = { top: 32, right: 8, bottom: 42, left: 56 };

function useMobileChartLayout() {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 768px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const onChange = (e) => setMobile(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return mobile;
}

function chartFontSizes(mobile) {
  if (mobile) {
    return { axisY: 14, axisX: 12, value: 13, compact: 11 };
  }
  return { axisY: 11, axisX: 10, value: 11, compact: 9 };
}

function formatEuroAxis(n) {
  if (n >= 1000) return `€${(n / 1000).toFixed(1)}k`;
  return `€${Math.round(n)}`;
}

function formatBarValue(n) {
  const v = Number(n) || 0;
  if (v >= 10000) return `€${Math.round(v / 1000)}k`;
  if (v >= 1000) return `€${(v / 1000).toFixed(1).replace('.', ',')}k`;
  return `€${Math.round(v).toLocaleString('it-IT')}`;
}

function IncassatoBarChart({ series, period, highlightIndex }) {
  const mobile = useMobileChartLayout();
  const pad = mobile ? PAD_MOBILE : PAD;
  const fs = chartFontSizes(mobile);
  const plotW = CHART_W - pad.left - pad.right;
  const plotH = CHART_H - pad.top - pad.bottom;

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
  }, [series, plotW, plotH]);

  if (!chart) {
    return (
      <div className="incassato-chart-empty">Nessun incasso registrato nel periodo selezionato.</div>
    );
  }

  const { bars, maxVal, yTicks } = chart;

  return (
    <svg
      className="incassato-chart-svg"
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      role="img"
      aria-label={period === 'year' ? 'Incassato per mese nell anno corrente' : 'Incassato giornaliero nel mese corrente'}
    >
      {yTicks.map((tick) => {
        const y = pad.top + plotH - (tick / maxVal) * plotH;
        return (
          <g key={tick}>
            <line x1={pad.left} y1={y} x2={CHART_W - pad.right} y2={y} className="incassato-chart-grid" />
            <text
              x={pad.left - 8}
              y={y + 4}
              textAnchor="end"
              className="incassato-chart-axis"
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
        const valueClass = [
          'incassato-bar-value',
          isHighlight ? 'incassato-bar-value--highlight' : '',
          labelInside ? 'incassato-bar-value--inside' : '',
          b.w < (mobile ? 22 : 18) ? 'incassato-bar-value--compact' : '',
        ].filter(Boolean).join(' ');

        return (
          <g key={b.label + b.i}>
            {b.h > 0 && (
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={3}
                className={isHighlight ? 'incassato-bar incassato-bar--highlight' : 'incassato-bar'}
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
                fontSize={b.w < (mobile ? 22 : 18) ? fs.compact : fs.value}
              >
                {label}
              </text>
            )}
            {(series.length <= 12 || b.i % Math.ceil(series.length / 12) === 0 || b.i === series.length - 1) && (
              <text
                x={b.x + b.w / 2}
                y={CHART_H - (mobile ? 10 : 8)}
                textAnchor="middle"
                className="incassato-chart-axis incassato-chart-axis--x"
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

export default function IncassatoDashboardSection({ closures }) {
  const { user } = useAuth();
  const username = user?.username;
  const now = new Date();
  const year = now.getFullYear();
  const monthIndex = now.getMonth();

  const departments = useMemo(() => collectDepartmentsFromClosures(closures), [closures]);

  const [period, setPeriod] = useState(() =>
    loadUserPreference(username, PREF_INCASSATO_PERIOD, PERIOD_VALUES, DEFAULT_PERIOD),
  );
  const [scope, setScope] = useState(INCASSATO_SCOPE_ALL);

  useEffect(() => {
    setPeriod(loadUserPreference(username, PREF_INCASSATO_PERIOD, PERIOD_VALUES, DEFAULT_PERIOD));
  }, [username]);

  useEffect(() => {
    const keys = [INCASSATO_SCOPE_ALL, ...collectDepartmentsFromClosures(closures).map((d) => d.key)];
    const saved = loadUserPreference(username, PREF_INCASSATO_SCOPE, keys, INCASSATO_SCOPE_ALL);
    setScope(keys.includes(saved) ? saved : INCASSATO_SCOPE_ALL);
  }, [username, closures]);

  const handlePeriodChange = (next) => {
    setPeriod(next);
    saveUserPreference(username, PREF_INCASSATO_PERIOD, next);
  };

  const handleScopeChange = (next) => {
    setScope(next);
    saveUserPreference(username, PREF_INCASSATO_SCOPE, next);
  };

  const deptKey = scope || INCASSATO_SCOPE_ALL;
  const deptLabel = departments.find((d) => d.key === deptKey)?.label;
  const isTotalScope = !deptKey;

  const monthTotal = useMemo(
    () => getTotalIncassatoForMonth(closures, year, monthIndex, deptKey),
    [closures, year, monthIndex, deptKey],
  );
  const yearTotal = useMemo(
    () => getTotalIncassatoForYear(closures, year, deptKey),
    [closures, year, deptKey],
  );

  const dailySeries = useMemo(
    () => getDailyIncassatoSeries(closures, year, monthIndex, deptKey),
    [closures, year, monthIndex, deptKey],
  );
  const monthlySeries = useMemo(
    () => getMonthlyIncassatoSeries(closures, year, deptKey),
    [closures, year, deptKey],
  );

  const mainTotal = period === 'year' ? yearTotal : monthTotal;
  const chartSeries = period === 'year' ? monthlySeries : dailySeries;
  const monthName = getCurrentMonthName();
  const dailyAvg = averageNonZeroValues(dailySeries);
  const monthlyAvg = averageNonZeroValues(monthlySeries.filter((m) => m.value > 0));

  const highlightIndex = period === 'year' ? monthIndex : null;

  return (
    <section className="incassato-section" aria-labelledby="incassato-heading">
      <div className="incassato-section__header">
        <div className="incassato-section__intro">
          <div className="incassato-section__title-row">
            <TrendingUp size={22} className="incassato-section__icon" aria-hidden />
            <h2 id="incassato-heading" className="incassato-section__title">
              {isTotalScope ? 'Totale incassato' : `Incassato — ${deptLabel}`}
            </h2>
          </div>
          <p className="incassato-section__hint">
            {isTotalScope ? (
              <>Somma delle <strong>entrate di tutti i reparti</strong> dalle chiusure cassa.</>
            ) : (
              <>Entrate del reparto <strong>{deptLabel}</strong> dalle chiusure cassa.</>
            )}
            {period === 'month'
              ? ` Mese di ${monthName}.`
              : ` Anno ${year} (andamento mensile).`}
            {' '}Periodo e reparto scelti vengono ricordati su questo dispositivo.
          </p>
        </div>
        <div className="incassato-section__filters">
          <div className="incassato-section__filter">
            <label htmlFor="incassato-scope" className="incassato-section__filter-label">Visualizza</label>
            <select
              id="incassato-scope"
              className="reparti-chart-select"
              value={scope}
              onChange={(e) => handleScopeChange(e.target.value)}
            >
              <option value={INCASSATO_SCOPE_ALL}>Totale incassato</option>
              {departments.map((d) => (
                <option key={d.key} value={d.key}>{d.label}</option>
              ))}
            </select>
          </div>
          <div className="incassato-section__filter">
            <label htmlFor="incassato-period" className="incassato-section__filter-label">Periodo</label>
            <select
              id="incassato-period"
              className="reparti-chart-select"
              value={period}
              onChange={(e) => handlePeriodChange(e.target.value)}
            >
              {INCASSATO_PERIOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="incassato-section__body">
        <div className="incassato-kpis">
          <div className="incassato-kpi incassato-kpi--primary">
            <span className="incassato-kpi__label">
              {period === 'year' ? `Totale ${year}` : `Totale ${monthName}`}
            </span>
            <span className="incassato-kpi__value">€ {mainTotal.toFixed(2)}</span>
          </div>
          <div className="incassato-kpi">
            <span className="incassato-kpi__label">Anno {year}</span>
            <span className="incassato-kpi__value incassato-kpi__value--muted">€ {yearTotal.toFixed(2)}</span>
          </div>
          <div className="incassato-kpi">
            <span className="incassato-kpi__label">
              {period === 'year' ? 'Media mensile' : 'Media giornaliera (mese)'}
            </span>
            <span className="incassato-kpi__value incassato-kpi__value--muted">
              € {(period === 'year' ? monthlyAvg : dailyAvg)?.toFixed(2) ?? '—'}
            </span>
          </div>
        </div>

        <div className="incassato-chart-wrap">
          <h3 className="incassato-chart-title">
            {period === 'year'
              ? `${isTotalScope ? 'Incassato' : deptLabel} per mese — ${year}`
              : `${isTotalScope ? 'Incassato' : deptLabel} giornaliero — ${monthName}`}
          </h3>
          <IncassatoBarChart
            series={chartSeries}
            period={period}
            highlightIndex={highlightIndex}
          />
        </div>
      </div>
    </section>
  );
}
