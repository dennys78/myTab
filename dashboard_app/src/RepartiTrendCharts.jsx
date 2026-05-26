import { useEffect, useMemo, useState } from 'react';
import { REPARTI_CHART_PERIOD_OPTIONS, getRepartiChartPeriodLabel } from './dateFilters';
import {
  CHART_SLOT_COLORS,
  averageSeriesValue,
  collectDepartmentsFromClosures,
  getDeptLabel,
  getFilteredClosureSeries,
  resolveChartDeptPair,
} from './repartiChartUtils';
import { useAuth } from './auth';
import { loadUserPreference, loadUserPreferenceJson, saveUserPreference, saveUserPreferenceJson } from './userPreferences';

const REPARTI_PERIOD_VALUES = REPARTI_CHART_PERIOD_OPTIONS.map((o) => o.value);
const DEFAULT_REPARTI_PERIOD = 'month';
const PREF_REPARTI_PERIOD = 'repartiChartPeriod';
const PREF_REPARTI_DEPTS = 'repartiChartDepts';

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

function MiniLineChart({ title, subtitle, color, series, periodLabel, average }) {
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
          <div className="reparti-chart-card__stats">
            <span className="reparti-chart-card__stat">Media ({periodLabel}): —</span>
          </div>
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
        <div className="reparti-chart-card__stats">
          <span className="reparti-chart-card__stat" style={{ color }}>
            Media ({periodLabel}): € {(average ?? 0).toFixed(2)}
          </span>
          <span className="reparti-chart-card__stat reparti-chart-card__stat--muted">
            Ultimo giorno: € {series[series.length - 1].value.toFixed(2)}
          </span>
        </div>
      </header>
      <svg
        className="reparti-chart-svg"
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        role="img"
        aria-label={`${title}: andamento saldo per giorno`}
      >
        {yTicks.map((tick) => {
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

function ChartFilterField({ id, label, children, footer }) {
  return (
    <div className="reparti-charts-section__filter">
      <label htmlFor={id} className="reparti-charts-section__filter-label">{label}</label>
      {children}
      <div className="reparti-chart-filter-footer">{footer}</div>
    </div>
  );
}

function DeptSelect({ id, label, value, options, excludeKey, onChange, disabled, periodLabel, average }) {
  return (
    <ChartFilterField
      id={id}
      label={label}
      footer={(
        <span className="reparti-chart-dept-avg" title={`Media saldo giornaliero nel ${periodLabel}`}>
          Media ({periodLabel}): {average != null ? `€ ${average.toFixed(2)}` : '—'}
        </span>
      )}
    >
      <select
        id={id}
        className="reparti-chart-select"
        value={value || ''}
        disabled={disabled || !options.length}
        onChange={(e) => onChange(e.target.value)}
      >
        {!value && <option value="">—</option>}
        {options.map((d) => (
          <option key={d.key} value={d.key} disabled={excludeKey && d.key === excludeKey}>
            {d.label}
          </option>
        ))}
      </select>
    </ChartFilterField>
  );
}

export default function RepartiTrendCharts({ closures }) {
  const { user } = useAuth();
  const username = user?.username;

  const departments = useMemo(() => collectDepartmentsFromClosures(closures), [closures]);

  const [period, setPeriod] = useState(() =>
    loadUserPreference(username, PREF_REPARTI_PERIOD, REPARTI_PERIOD_VALUES, DEFAULT_REPARTI_PERIOD),
  );

  const [deptPair, setDeptPair] = useState(() =>
    resolveChartDeptPair(loadUserPreferenceJson(username, PREF_REPARTI_DEPTS, null), departments),
  );

  useEffect(() => {
    setPeriod(loadUserPreference(username, PREF_REPARTI_PERIOD, REPARTI_PERIOD_VALUES, DEFAULT_REPARTI_PERIOD));
  }, [username]);

  useEffect(() => {
    const saved = loadUserPreferenceJson(username, PREF_REPARTI_DEPTS, null);
    setDeptPair(resolveChartDeptPair(saved, departments));
  }, [username, departments]);

  const handlePeriodChange = (next) => {
    setPeriod(next);
    saveUserPreference(username, PREF_REPARTI_PERIOD, next);
  };

  const persistDeptPair = (pair) => {
    setDeptPair(pair);
    saveUserPreferenceJson(username, PREF_REPARTI_DEPTS, pair);
  };

  const handleDept1Change = (key) => {
    const next = [key, deptPair[1]];
    if (key === deptPair[1] && departments.length > 1) {
      const alt = departments.find((d) => d.key !== key)?.key;
      next[1] = alt || key;
    }
    persistDeptPair(next);
  };

  const handleDept2Change = (key) => {
    const next = [deptPair[0], key];
    if (key === deptPair[0] && departments.length > 1) {
      const alt = departments.find((d) => d.key !== key)?.key;
      next[0] = alt || key;
    }
    persistDeptPair(next);
  };

  const periodLabel = getRepartiChartPeriodLabel(period);
  const [deptKey1, deptKey2] = deptPair;
  const label1 = getDeptLabel(departments, deptKey1);
  const label2 = getDeptLabel(departments, deptKey2);

  const series1 = useMemo(
    () => (deptKey1 ? getFilteredClosureSeries(closures, period, deptKey1) : []),
    [closures, period, deptKey1],
  );
  const series2 = useMemo(
    () => (deptKey2 ? getFilteredClosureSeries(closures, period, deptKey2) : []),
    [closures, period, deptKey2],
  );

  const average1 = useMemo(() => averageSeriesValue(series1), [series1]);
  const average2 = useMemo(() => averageSeriesValue(series2), [series2]);

  const hasDepartments = departments.length > 0;

  return (
    <section className="reparti-charts-section" aria-labelledby="reparti-charts-heading">
      <div className="reparti-charts-section__header">
        <div>
          <h2 id="reparti-charts-heading" className="reparti-charts-section__title">Andamento reparti</h2>
          <p className="reparti-charts-section__hint">
            {hasDepartments ? (
              <>
                Andamento del {periodLabel} per <strong>{label1}</strong> e <strong>{label2}</strong>.
                Periodo e reparti scelti vengono ricordati su questo dispositivo.
              </>
            ) : (
              'Registra almeno una chiusura con voci reparto per visualizzare i grafici.'
            )}
          </p>
        </div>
        <div className="reparti-charts-section__filters">
          <DeptSelect
            id="reparti-chart-dept-1"
            label="Grafico 1"
            value={deptKey1}
            options={departments}
            excludeKey={deptKey2}
            onChange={handleDept1Change}
            disabled={!hasDepartments}
            periodLabel={periodLabel}
            average={average1}
          />
          <DeptSelect
            id="reparti-chart-dept-2"
            label="Grafico 2"
            value={deptKey2}
            options={departments}
            excludeKey={deptKey1}
            onChange={handleDept2Change}
            disabled={!hasDepartments}
            periodLabel={periodLabel}
            average={average2}
          />
          <ChartFilterField
            id="reparti-chart-period"
            label="Periodo"
            footer={<span className="reparti-chart-dept-avg reparti-chart-dept-avg--placeholder" aria-hidden="true" />}
          >
            <select
              id="reparti-chart-period"
              className="reparti-chart-select"
              value={period}
              onChange={(e) => handlePeriodChange(e.target.value)}
            >
              {REPARTI_CHART_PERIOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </ChartFilterField>
        </div>
      </div>
      {hasDepartments && (
        <div className="reparti-charts-grid">
          <MiniLineChart
            title={label1}
            subtitle="Saldo cassa per giorno"
            color={CHART_SLOT_COLORS[0]}
            series={series1}
            periodLabel={periodLabel}
            average={average1}
          />
          <MiniLineChart
            title={label2}
            subtitle="Saldo cassa per giorno"
            color={CHART_SLOT_COLORS[1]}
            series={series2}
            periodLabel={periodLabel}
            average={average2}
          />
        </div>
      )}
    </section>
  );
}
