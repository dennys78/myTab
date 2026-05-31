import { useCallback, useEffect, useState } from 'react';
import { Bell, CheckCircle, Loader2, AlertCircle, Send } from 'lucide-react';
import {
  ensurePushSubscription,
  fetchPushStatus,
  isDevicePushRegistrationCurrent,
  isWebPushSupported,
  pushUnavailableReason,
  sendTestPush,
  waitForServiceWorker,
} from './webPush';

const REASON_LABELS = {
  insecure: 'Serve HTTPS (es. https://www.my-tab.uk). Su http://…:8080 le push non funzionano.',
  unsupported: 'Browser non supportato per le notifiche push.',
  'ios-not-pwa': 'Su iPhone installa myTab con Aggiungi a Home, poi apri l\'app dall\'icona (iOS 16.4+).',
  denied: 'Notifiche bloccate. Abilitale nelle impostazioni del browser/sistema.',
  default: 'Permesso notifiche non ancora concesso.',
  'no-sw': 'App non pronta. Ricarica la pagina o reinstalla la PWA.',
  config: 'Server push non configurato. Contatta l\'amministratore.',
  'config-error': 'Errore configurazione push sul server.',
  save: 'Registrazione sul server fallita. Riprova.',
};

export default function PushNotificheCard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [registering, setRegistering] = useState(false);
  const [registerResult, setRegisterResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const refresh = useCallback(() => {
    setLoading(true);
    (async () => {
      let endpoint = '';
      try {
        if (isWebPushSupported()) {
          const registration = await waitForServiceWorker(5000);
          const subscription = await registration?.pushManager?.getSubscription();
          endpoint = subscription?.endpoint || '';
        }
      } catch {
        /* ignore */
      }
      return fetchPushStatus(endpoint);
    })()
      .then((data) => setStatus(data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const blocked = pushUnavailableReason();
  const permission = typeof Notification !== 'undefined' ? Notification.permission : 'default';
  const registrationStale = Boolean(
    status?.vapid_public_key
    && status?.vapid_configured
    && !isDevicePushRegistrationCurrent(status.vapid_public_key),
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!status?.vapid_public_key || !status?.vapid_configured || blocked || permission !== 'granted') {
      return;
    }
    if (isDevicePushRegistrationCurrent(status.vapid_public_key)) return;

    ensurePushSubscription({ requestPermission: false, forceRenew: true })
      .then((result) => {
        if (result.ok) refresh();
      })
      .catch(() => {});
  }, [status, blocked, permission, refresh]);

  const handleRegister = () => {
    setRegistering(true);
    setRegisterResult(null);
    ensurePushSubscription({ requestPermission: true, forceRenew: true })
      .then((result) => {
        if (result.ok) {
          setRegisterResult({ ok: true });
          refresh();
        } else {
          setRegisterResult({
            ok: false,
            message: REASON_LABELS[result.reason] || `Errore: ${result.reason}`,
          });
        }
      })
      .catch(() => {
        setRegisterResult({ ok: false, message: 'Errore di rete durante la registrazione.' });
      })
      .finally(() => {
        setRegistering(false);
        setTimeout(() => setRegisterResult(null), 8000);
      });
  };

  const handleTest = () => {
    setTesting(true);
    setTestResult(null);
    sendTestPush()
      .then((result) => {
        if (result.ok) {
          const {
            push_sent: sent,
            push_failed: failed,
            push_removed: removed,
            company_devices: total,
            push_errors: errors,
          } = result;
          let message;
          if (sent === total && total > 0) {
            message = `Notifica di test inviata a tutti i ${total} dispositivi registrati.`;
          } else if (sent > 0) {
            message = `Notifica inviata a ${sent} dispositivo${sent === 1 ? '' : 'i'} su ${total}.`;
            if (failed > 0) {
              message += ` ${failed} non raggiunti: apri myTab su ogni telefono e premi «Registra questo smartphone».`;
            }
            if (removed > 0) {
              message += ` ${removed} registrazione${removed === 1 ? ' obsoleta rimossa' : 'i obsolete rimosse'}.`;
            }
          } else if (errors?.length) {
            message = `Nessun dispositivo ha ricevuto la notifica (${total} registrati). ${errors[0]}`;
          } else {
            message = `Nessun dispositivo ha ricevuto la notifica (${total} registrati). Riregistra ogni smartphone.`;
          }
          setTestResult({ ok: sent > 0, message });
          if (removed > 0) refresh();
        } else {
          setTestResult({ ok: false, message: result.error || 'Invio test fallito.' });
        }
      })
      .catch(() => {
        setTestResult({ ok: false, message: 'Errore di rete durante l\'invio del test.' });
      })
      .finally(() => {
        setTesting(false);
        setTimeout(() => setTestResult(null), 10000);
      });
  };

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
        <Bell size={20} color="var(--accent)" />
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Notifiche browser</h2>
        {status?.user_devices > 0 && status?.devices?.some((d) => d.is_current) && (
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#22c55e', fontSize: '0.8rem', fontWeight: 600 }}>
            <CheckCircle size={14} /> Attivo su questo dispositivo
          </span>
        )}
      </div>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem', lineHeight: 1.5 }}>
        Ogni smartphone va registrato separatamente: apri myTab, accetta le notifiche e premi il pulsante sotto.
        Su iPhone installa la PWA (Aggiungi a Home) e usa HTTPS.
      </p>

      {blocked && (
        <div style={{ background: 'rgba(245,158,11,0.12)', border: '1px solid var(--warning)', padding: '0.75rem', borderRadius: '8px', color: 'var(--warning)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          {REASON_LABELS[blocked]}
        </div>
      )}

      {!blocked && permission === 'denied' && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.75rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          {REASON_LABELS.denied}
        </div>
      )}

      {!blocked && registrationStale && (
        <div style={{ background: 'rgba(245,158,11,0.12)', border: '1px solid var(--warning)', padding: '0.75rem', borderRadius: '8px', color: 'var(--warning)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          Questo dispositivo usa una registrazione push obsoleta. Premi «Registra questo smartphone» o attendi la sincronizzazione automatica.
        </div>
      )}

      {registerResult && (
        <div style={{
          background: registerResult.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${registerResult.ok ? '#22c55e' : 'var(--danger)'}`,
          padding: '0.75rem',
          borderRadius: '8px',
          color: registerResult.ok ? '#22c55e' : 'var(--danger)',
          marginBottom: '1rem',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          {registerResult.ok ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
          {registerResult.ok ? 'Dispositivo registrato per le notifiche push.' : registerResult.message}
        </div>
      )}

      {testResult && (
        <div style={{
          background: testResult.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${testResult.ok ? '#22c55e' : 'var(--danger)'}`,
          padding: '0.75rem',
          borderRadius: '8px',
          color: testResult.ok ? '#22c55e' : 'var(--danger)',
          marginBottom: '1rem',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          {testResult.ok ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
          {testResult.message}
        </div>
      )}

      <div style={{ display: 'grid', gap: '0.35rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
        <div>Permesso browser: <strong>{permission}</strong></div>
        <div>Push supportate: <strong>{isWebPushSupported() ? 'sì' : 'no'}</strong></div>
        {loading ? (
          <div style={{ color: 'var(--text-muted)' }}>Caricamento stato…</div>
        ) : status && (
          <>
            <div>Totale dispositivi azienda: <strong>{status.company_devices}</strong></div>
            <div>I tuoi dispositivi registrati: <strong>{status.user_devices}</strong></div>
            {!status.vapid_configured && (
              <div style={{ color: 'var(--danger)' }}>
                Server push non pronto{status.vapid_error ? `: ${status.vapid_error}` : ''}. Esegui rebuild backend con pywebpush.
              </div>
            )}
            {status.devices?.length > 0 && (
              <div style={{ marginTop: '0.5rem' }}>
                <div style={{ color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Elenco dispositivi registrati:</div>
                <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'grid', gap: '0.25rem' }}>
                  {status.devices.map((device) => (
                    <li key={`${device.username}-${device.device}-${device.updated_at}`}>
                      <strong>{device.username}</strong> · {device.device}
                      {device.is_current ? ' · questo dispositivo' : ''}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
        <button
          type="button"
          onClick={handleRegister}
          disabled={registering || !!blocked}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.65rem 1rem',
            background: blocked ? 'var(--bg-dark)' : 'var(--accent)',
            color: blocked ? 'var(--text-muted)' : 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: blocked ? 'not-allowed' : 'pointer',
            fontWeight: 700,
            fontSize: '0.9rem',
          }}
        >
          {registering ? <Loader2 size={16} className="spin" /> : <Bell size={16} />}
          Registra questo smartphone
        </button>

        <button
          type="button"
          onClick={handleTest}
          disabled={
            testing
            || loading
            || !status?.vapid_configured
            || !status?.company_devices
          }
          title={
            !status?.company_devices
              ? 'Registra almeno un dispositivo prima del test'
              : 'Invia una notifica di prova a tutti i dispositivi registrati'
          }
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.65rem 1rem',
            background: 'var(--bg-dark)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            cursor: (testing || loading || !status?.vapid_configured || !status?.company_devices)
              ? 'not-allowed'
              : 'pointer',
            fontWeight: 600,
            fontSize: '0.9rem',
            opacity: (testing || loading || !status?.vapid_configured || !status?.company_devices) ? 0.55 : 1,
          }}
        >
          {testing ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
          Invia notifica di test
        </button>
      </div>
    </div>
  );
}
