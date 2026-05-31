import { useCallback, useEffect, useState } from 'react';
import { Bell, Sparkles, X } from 'lucide-react';
import { apiFetch } from './api';
import { filterUnseenDrafts, markDraftsSeen } from './telegramDraftNotifications';

const POLL_MS = 20_000;

function formatMoney(value) {
  return `€ ${Number(value).toFixed(2)}`;
}

function formatWhen(iso) {
  try {
    return new Date(iso).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function TelegramDraftNotification({
  companyId,
  enabled,
  currentView,
  onOpenAcquisition,
}) {
  const [unseen, setUnseen] = useState([]);
  const [dismissed, setDismissed] = useState(false);

  const refresh = useCallback(() => {
    if (!enabled || !companyId) {
      setUnseen([]);
      return;
    }
    apiFetch('/api/acquisition-drafts/')
      .then((r) => r.json())
      .then((d) => {
        if (d.status !== 'success') return;
        const pending = filterUnseenDrafts(companyId, d.data);
        setUnseen(pending);
        if (pending.length) setDismissed(false);
      })
      .catch(() => {});
  }, [companyId, enabled]);

  useEffect(() => {
    refresh();
    if (!enabled || !companyId) return undefined;
    const id = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh, enabled, companyId]);

  useEffect(() => {
    if (currentView !== 'acquisisci-ai' || !companyId) return;
    apiFetch('/api/acquisition-drafts/')
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success' && d.data?.length) {
          markDraftsSeen(companyId, d.data.map((item) => item.id));
          setUnseen([]);
          setDismissed(true);
        }
      })
      .catch(() => {});
  }, [currentView, companyId]);

  const handleOpen = () => {
    if (unseen.length) markDraftsSeen(companyId, unseen.map((d) => d.id));
    setUnseen([]);
    setDismissed(true);
    onOpenAcquisition?.();
  };

  const handleDismiss = () => {
    if (unseen.length) markDraftsSeen(companyId, unseen.map((d) => d.id));
    setUnseen([]);
    setDismissed(true);
  };

  if (!enabled || !unseen.length || dismissed) return null;

  const latest = unseen[0];
  const count = unseen.length;

  return (
    <div className="telegram-draft-banner" role="status" aria-live="polite">
      <div className="telegram-draft-banner__icon" aria-hidden="true">
        <Bell size={22} />
      </div>
      <div className="telegram-draft-banner__body">
        <strong className="telegram-draft-banner__title">
          {count === 1
            ? 'Foglio cassa da contabilizzare'
            : `${count} fogli cassa da contabilizzare`}
        </strong>
        <p className="telegram-draft-banner__text">
          {count === 1 ? (
            <>
              Da Telegram · <strong>{latest.operator || 'Operatore'}</strong>
              {' · '}{latest.photo_count} foto
              {latest.pag_pos_reale > 0 ? ` · POS ${formatMoney(latest.pag_pos_reale)}` : ''}
              {' · '}scassettato {formatMoney(latest.totale_scassettato)}
              {latest.created_at ? ` · ${formatWhen(latest.created_at)}` : ''}
            </>
          ) : (
            <>
              Ultimo foglio: <strong>{latest.operator || 'Operatore'}</strong>
              {' · '}{latest.photo_count} foto
              {latest.pag_pos_reale > 0 ? ` · POS ${formatMoney(latest.pag_pos_reale)}` : ''}
              {' · '}scassettato {formatMoney(latest.totale_scassettato)}
            </>
          )}
        </p>
        <div className="telegram-draft-banner__actions">
          <button type="button" className="telegram-draft-banner__primary" onClick={handleOpen}>
            <Sparkles size={16} />
            Apri Acquisisci con IA
          </button>
          <button type="button" className="telegram-draft-banner__ghost" onClick={handleDismiss}>
            Chiudi
          </button>
        </div>
      </div>
      <button
        type="button"
        className="telegram-draft-banner__close"
        onClick={handleDismiss}
        aria-label="Chiudi notifica"
      >
        <X size={18} />
      </button>
    </div>
  );
}
