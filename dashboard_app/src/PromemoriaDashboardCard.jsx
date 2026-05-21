import { useState } from 'react';
import { Bookmark, ChevronDown, Pencil } from 'lucide-react';

function formatVersamento(v) {
  return {
    date: new Date(v.date).toLocaleDateString('it-IT'),
    importo: Number(v.importo_versato).toFixed(2),
    note: v.note?.trim() || 'Nessuna nota',
  };
}

export default function PromemoriaDashboardCard({ versamenti, onSelect }) {
  const [open, setOpen] = useState(false);
  const list = versamenti.filter(v => v.ricorda_promemoria);

  if (list.length === 0) return null;

  const first = formatVersamento(list[0]);

  return (
    <div className={`stat-card stat-card-promemoria ${open ? 'stat-card-promemoria--open' : ''}`}>
      <button
        type="button"
        className="stat-card-promemoria-toggle"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <div className="stat-card-promemoria-head">
          <div className="stat-title">
            <Bookmark size={14} style={{ verticalAlign: '-2px', marginRight: '0.35rem' }} />
            Promemoria versamenti
            <span className="stat-promemoria-count">{list.length}</span>
          </div>
          <ChevronDown size={18} className={`stat-promemoria-chevron ${open ? 'is-open' : ''}`} />
        </div>
        {!open && (
          <div className="stat-promemoria-collapsed">
            <div className="stat-promemoria-meta">
              {first.date} · € {first.importo}
              {list.length > 1 && ` · +${list.length - 1} altri`}
            </div>
            <div className="stat-promemoria-note">{first.note}</div>
          </div>
        )}
      </button>

      {open && (
        <div className="stat-promemoria-expanded">
          <p className="stat-promemoria-hint">Tocca un movimento per aprirlo in modifica.</p>
          <ul className="promemoria-list">
            {list.map(v => {
              const f = formatVersamento(v);
              return (
                <li key={v.id}>
                  <button
                    type="button"
                    className="promemoria-list-item"
                    onClick={() => onSelect(v.id)}
                  >
                    <div className="promemoria-list-meta">
                      <span>{f.date}</span>
                      <span className="promemoria-list-importo">€ {f.importo}</span>
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
