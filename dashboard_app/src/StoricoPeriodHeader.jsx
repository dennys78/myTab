import { STORICO_PERIOD_OPTIONS } from './dateFilters';

export default function StoricoPeriodHeader({ title, value, onChange }) {
  return (
    <div className="storico-period-header">
      <h2 className="storico-period-title">{title}</h2>
      <div className="storico-period-controls">
        <label className="storico-period-label" htmlFor={`storico-filter-${title}`}>Periodo</label>
        <select
          id={`storico-filter-${title}`}
          className="storico-period-select"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {STORICO_PERIOD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
