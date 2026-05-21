import { useState } from 'react';
import { Bookmark, ChevronDown, Pencil, TrendingDown, TrendingUp } from 'lucide-react';

const TIPO_ENTRATA = 'ENTRATA';

function formatMovimento(m) {
  const isEntrata = m.tipo === TIPO_ENTRATA;
  return {
    date: new Date(`${m.date}T12:00:00`).toLocaleDateString('it-IT'),
    importo: isEntrata ? `+ € ${Number(m.importo).toFixed(2)}` : `− € ${Number(m.importo).toFixed(2)}`,
    tipoLabel: isEntrata ? 'Entrata' : 'Uscita',
    isEntrata,
    note: m.note?.trim() || 'Nessuna nota',
  };
}

function promemoriaMovimentiList(movimenti) {
  return [...movimenti]
    .filter(m => m.ricorda_promemoria === true || m.ricorda_promemoria === 1)
    .sort((a, b) => {
      const byDate = String(b.date).localeCompare(String(a.date));
      return byDate !== 0 ? byDate : (b.id ?? 0) - (a.id ?? 0);
    });
}

export default function PromemoriaMovimentiDashboardCard({ movimenti, onSelect }) {
  const [open, setOpen] = useState(false);
  const list = promemoriaMovimentiList(movimenti);

  if (list.length === 0) return null;

  return (
    <div className={`stat-card stat-card-promemoria-mov ${open ? 'stat-card-promemoria-mov--open' : ''}`}>
      <button
        type="button"
        className="stat-card-promemoria-toggle"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <div className="stat-card-promemoria-head">
          <div className="stat-title">
            <Bookmark size={14} style={{ verticalAlign: '-2px', marginRight: '0.35rem' }} />
            Promemoria movimenti
            <span className="stat-promemoria-count stat-promemoria-count--mov">{list.length}</span>
          </div>
          <ChevronDown size={18} className={`stat-promemoria-chevron ${open ? 'is-open' : ''}`} />
        </div>
        {!open && (
          <ul className="promemoria-preview-list" aria-label="Elenco promemoria movimenti">
            {list.map(m => {
              const f = formatMovimento(m);
              return (
                <li key={m.id} className={`promemoria-preview-item ${f.isEntrata ? 'promemoria-preview-item--entrata' : 'promemoria-preview-item--uscita'}`}>
                  <span className="promemoria-preview-meta">
                    {f.date} · {f.tipoLabel} · <span className={f.isEntrata ? 'mov-importo-entrata' : 'mov-importo-uscita'}>{f.importo}</span>
                  </span>
                  <span className="promemoria-preview-note">{f.note}</span>
                </li>
              );
            })}
          </ul>
        )}
      </button>

      {open && (
        <div className="stat-promemoria-expanded">
          <p className="stat-promemoria-hint">Tocca un movimento per aprirlo in modifica.</p>
          <ul className="promemoria-list">
            {list.map(m => {
              const f = formatMovimento(m);
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    className={`promemoria-list-item ${f.isEntrata ? 'promemoria-list-item--entrata' : 'promemoria-list-item--uscita'}`}
                    onClick={() => onSelect(m.id)}
                  >
                    <div className="promemoria-list-meta">
                      <span>
                        {f.isEntrata ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                        {' '}{f.date} · {f.tipoLabel}
                      </span>
                      <span className={f.isEntrata ? 'mov-importo-entrata' : 'mov-importo-uscita'}>{f.importo}</span>
                    </div>
                    <div className="promemoria-list-note">{f.note}</div>
                    <span className="promemoria-list-edit">
                      <Pencil size={14} /> Modifica
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
