import { useEffect, useMemo, useState } from 'react';
import { REPARTI_CHART_PERIOD_OPTIONS, getRepartiChartPeriodLabel } from './dateFilters';
import {
  CHART_SLOT_COLORS,
  averageSeriesValue,
  collectDepartmentsFromClosures,
  countClosureDaysInPeriod,
  getDeptLabel,
  getFilteredClosureSeries,
  resolveChartDeptPair,
} from './repartiChartUtils';
import { useAuth } from './auth';
import { loadUserPreference, loadUserPreferenceJson, saveUserPreference, saveUserPreferenceJson } from './userPreferences';
import BarColumnChart from './BarColumnChart';
import { BAR_CHART_H } from './chartBarShared';

const REPARTI_PERIOD_VALUES = REPARTI_CHART_PERIOD_OPTIONS.map((o) => o.value);
const DEFAULT_REPARTI_PERIOD = 'month';
const PREF_REPARTI_PERIOD = 'repartiChartPeriod';
const PREF_REPARTI_DEPTS = 'repartiChartDepts';

function formatShortDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
}

function MiniBarChart({ title, subtitle, color, series, periodLabel, average }) {
  const barSeries = useMemo(
    () => series.map((p) => ({
      label: formatShortDate(p.date),
      value: p.value,
    })),
    [series],
  );

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
      <BarColumnChart
        series={barSeries}
        chartH={BAR_CHART_H}
        barColor={color}
        barMutedOpacity={0.58}
        ariaLabel={`${title}: entrate per giorno`}
        svgClassName="bar-column-chart-svg reparti-chart-svg"
        emptyClassName="reparti-chart-empty"
      />
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
        <span className="reparti-chart-dept-avg" title={`Media entrate giornaliere nel ${periodLabel}`}>
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

  const periodDayCount = useMemo(() => countClosureDaysInPeriod(closures, period), [closures, period]);

  const average1 = useMemo(() => averageSeriesValue(series1, periodDayCount), [series1, periodDayCount]);
  const average2 = useMemo(() => averageSeriesValue(series2, periodDayCount), [series2, periodDayCount]);

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
          <MiniBarChart
            title={label1}
            subtitle="Entrate per giorno"
            color={CHART_SLOT_COLORS[0]}
            series={series1}
            periodLabel={periodLabel}
            average={average1}
          />
          <MiniBarChart
            title={label2}
            subtitle="Entrate per giorno"
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
