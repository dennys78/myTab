import { useCallback, useEffect, useState } from 'react';
import { Bell, CheckCircle, Loader2 } from 'lucide-react';
import {
  ensurePushSubscription,
  fetchPushStatus,
  pushUnavailableReason,
  waitForServiceWorker,
} from './webPush';

const REASON_LABELS = {
  insecure: 'Serve HTTPS per le notifiche push.',
  unsupported: 'Browser non supportato.',
  denied: 'Notifiche bloccate nel browser.',
  default: 'Permesso non concesso.',
  'no-sw': 'App non pronta. Ricarica la pagina.',
  config: 'Push non configurato sul server.',
  'config-error': 'Errore configurazione push.',
  save: 'Registrazione sul server fallita.',
};

export default function PushNotifyButton() {
  const [checking, setChecking] = useState(true);
  const [activating, setActivating] = useState(false);
  const [active, setActive] = useState(false);
  const [denied, setDenied] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const refresh = useCallback(async () => {
    setChecking(true);
    const unavailable = pushUnavailableReason();
    if (unavailable === 'insecure' || unavailable === 'unsupported') {
      setHidden(true);
      setChecking(false);
      return;
    }
    setHidden(false);
    setDenied(unavailable === 'denied' || Notification.permission === 'denied');

    let endpoint = '';
    try {
      const registration = await waitForServiceWorker(5000);
      const subscription = await registration?.pushManager?.getSubscription();
      endpoint = subscription?.endpoint || '';
    } catch {
      /* ignore */
    }

    const status = await fetchPushStatus(endpoint).catch(() => null);
    const isCurrent = Boolean(status?.devices?.some((d) => d.is_current));
    setActive(Notification.permission === 'granted' && isCurrent);
    setChecking(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleActivate = () => {
    if (activating || checking || denied) return;
    setActivating(true);
    setFeedback(null);
    ensurePushSubscription({ requestPermission: true, forceRenew: true })
      .then((result) => {
        if (result.ok) {
          setActive(true);
          setFeedback({ ok: true, text: 'Notifiche attive e dispositivo registrato.' });
        } else {
          setDenied(result.reason === 'denied');
          setFeedback({
            ok: false,
            text: REASON_LABELS[result.reason] || 'Attivazione notifiche fallita.',
          });
        }
        return refresh();
      })
      .catch(() => {
        setFeedback({ ok: false, text: 'Errore di rete durante l\'attivazione.' });
      })
      .finally(() => {
        setActivating(false);
        setTimeout(() => setFeedback(null), 6000);
      });
  };

  if (hidden) return null;

  const label = checking
    ? 'Verifica notifiche…'
    : denied
      ? 'Notifiche bloccate'
      : active
        ? 'Notifiche attive'
        : 'Attiva notifiche';

  return (
    <div style={{ marginBottom: '0.5rem' }}>
      {feedback && (
        <div style={{
          fontSize: '0.72rem',
          marginBottom: '0.35rem',
          color: feedback.ok ? '#22c55e' : 'var(--danger)',
          lineHeight: 1.35,
        }}>
          {feedback.text}
        </div>
      )}
      <button
        type="button"
        onClick={handleActivate}
        disabled={checking || activating || denied}
        title={
          denied
            ? 'Abilita le notifiche nelle impostazioni del browser'
            : active
              ? 'Dispositivo registrato per le notifiche push'
              : 'Attiva le notifiche e registra questo dispositivo'
        }
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          width: '100%',
          padding: '0.5rem 0.6rem',
          background: active ? 'rgba(34,197,94,0.12)' : 'transparent',
          border: `1px solid ${active ? '#22c55e' : 'var(--border)'}`,
          color: active ? '#22c55e' : denied ? 'var(--text-muted)' : 'var(--text-main)',
          borderRadius: '6px',
          cursor: (checking || activating || denied) ? 'not-allowed' : 'pointer',
          fontSize: '0.85rem',
          opacity: (checking || activating || denied) ? 0.65 : 1,
        }}
      >
        {activating || checking ? (
          <Loader2 size={15} className="spin" />
        ) : active ? (
          <CheckCircle size={15} />
        ) : (
          <Bell size={15} />
        )}
        {label}
      </button>
    </div>
  );
}
