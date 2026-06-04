import { useEffect, useMemo, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { useAuth } from './auth';
import { loadUserPreference, saveUserPreference } from './userPreferences';
import { collectDepartmentsFromClosures } from './repartiChartUtils';
import BarColumnChart from './BarColumnChart';
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
              ? <> Media giornaliera (giorni con incasso): <strong>€ {dailyAvg.toFixed(2)}</strong>.</>
              : <> Media mensile (mesi con incasso): <strong>€ {monthlyAvg.toFixed(2)}</strong>.</>}
          </p>
        </div>
        <div className="incassato-section__filters">
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
          <div className="incassato-section__filter">
            <label htmlFor="incassato-scope" className="incassato-section__filter-label">Reparto</label>
            <select
              id="incassato-scope"
              className="reparti-chart-select"
              value={scope}
              onChange={(e) => handleScopeChange(e.target.value)}
            >
              <option value={INCASSATO_SCOPE_ALL}>Totale (tutti i reparti)</option>
              {departments.map((d) => (
                <option key={d.key} value={d.key}>{d.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="incassato-kpis">
        <div className="incassato-kpi incassato-kpi--primary">
          <span className="incassato-kpi__label">
            {period === 'year' ? `Totale ${year}` : `${monthName} ${year}`}
          </span>
          <span className="incassato-kpi__value">€ {mainTotal.toFixed(2)}</span>
        </div>
        <div className="incassato-kpi">
          <span className="incassato-kpi__label">
            {period === 'year' ? 'Media mensile' : 'Media giornaliera'}
          </span>
          <span className="incassato-kpi__value incassato-kpi__value--muted">
            € {(period === 'year' ? monthlyAvg : dailyAvg).toFixed(2)}
          </span>
        </div>
      </div>

      <div className="incassato-chart-wrap">
        <h3 className="incassato-chart-title">
          {period === 'year' ? `Incassato per mese — ${year}` : `Incassato giornaliero — ${monthName} ${year}`}
        </h3>
        <BarColumnChart
          series={chartSeries}
          barColor="#22c55e"
          highlightIndex={highlightIndex}
          ariaLabel={period === 'year' ? 'Incassato per mese nell anno corrente' : 'Incassato giornaliero nel mese corrente'}
          svgClassName="bar-column-chart-svg incassato-chart-svg"
          emptyClassName="incassato-chart-empty"
        />
      </div>
    </section>
  );
}
