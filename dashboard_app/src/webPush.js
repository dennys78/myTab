import { apiFetch } from './api';

export const VAPID_STORAGE_KEY = 'mytab_registered_vapid_public_key';

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from([...raw], (char) => char.charCodeAt(0));
}

export function isWebPushSupported() {
  return (
    typeof window !== 'undefined'
    && window.isSecureContext
    && 'Notification' in window
    && 'serviceWorker' in navigator
    && 'PushManager' in window
  );
}

export function pushUnavailableReason() {
  if (typeof window === 'undefined') return 'unsupported';
  if (!window.isSecureContext) return 'insecure';
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
    return 'unsupported';
  }
  return null;
}

export function getStoredVapidPublicKey() {
  try {
    return localStorage.getItem(VAPID_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function isDevicePushRegistrationCurrent(serverPublicKey) {
  if (!serverPublicKey) return false;
  return getStoredVapidPublicKey() === serverPublicKey;
}

export async function waitForServiceWorker(timeoutMs = 15000) {
  if (!('serviceWorker' in navigator)) return null;
  try {
    const ready = navigator.serviceWorker.ready;
    const timeout = new Promise((_, reject) => {
      window.setTimeout(() => reject(new Error('service worker timeout')), timeoutMs);
    });
    return await Promise.race([ready, timeout]);
  } catch {
    return null;
  }
}

export async function subscribeWebPush({ requestPermission = true, forceRenew = false } = {}) {
  const blocked = pushUnavailableReason();
  if (blocked) {
    return { ok: false, reason: blocked };
  }

  let permission = Notification.permission;
  if (permission === 'default' && requestPermission) {
    permission = await Notification.requestPermission();
  }
  if (permission !== 'granted') {
    return { ok: false, reason: permission === 'denied' ? 'denied' : 'default' };
  }

  const registration = await waitForServiceWorker();
  if (!registration?.pushManager) {
    return { ok: false, reason: 'no-sw' };
  }

  const keyRes = await apiFetch('/api/push/vapid-public-key/');
  const keyData = await keyRes.json();
  if (keyData.status !== 'success' || !keyData.data?.public_key) {
    return { ok: false, reason: keyData.error ? 'config-error' : 'config' };
  }

  const serverPublicKey = keyData.data.public_key;
  const storedKey = getStoredVapidPublicKey();
  const needsRenew = forceRenew || !storedKey || storedKey !== serverPublicKey;

  let subscription = await registration.pushManager.getSubscription();
  if (needsRenew && subscription) {
    try {
      await subscription.unsubscribe();
    } catch {
      /* ignore */
    }
    subscription = null;
  }

  const subscribeOptions = {
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(serverPublicKey),
  };

  if (!subscription) {
    try {
      subscription = await registration.pushManager.subscribe(subscribeOptions);
    } catch {
      const stale = await registration.pushManager.getSubscription();
      if (stale) {
        try {
          await stale.unsubscribe();
        } catch {
          /* ignore */
        }
      }
      subscription = await registration.pushManager.subscribe(subscribeOptions);
    }
  }

  const body = subscription.toJSON();
  const saveRes = await apiFetch('/api/push/subscribe/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const saveData = await saveRes.json();
  if (saveData.status !== 'success') {
    return { ok: false, reason: saveData.error || 'save' };
  }

  try {
    localStorage.setItem(VAPID_STORAGE_KEY, serverPublicKey);
  } catch {
    /* ignore */
  }

  return { ok: true, endpoint: body.endpoint, renewed: needsRenew };
}

/** Registra o aggiorna la sottoscrizione push di questo dispositivo sul server. */
export async function ensurePushSubscription(options = {}) {
  return subscribeWebPush(options);
}

export async function fetchPushStatus() {
  const res = await apiFetch('/api/push/status/');
  const data = await res.json();
  if (data.status !== 'success') return null;
  return data.data;
}

export async function sendTestPush() {
  const res = await apiFetch('/api/push/test/', { method: 'POST' });
  const data = await res.json();
  if (data.status !== 'success') {
    return { ok: false, error: data.error || 'Invio fallito' };
  }
  return { ok: true, ...data.data };
}

export async function showLocalPushNotification(payload) {
  if (Notification.permission !== 'granted') return false;
  const registration = await waitForServiceWorker(5000);
  if (!registration?.showNotification) return false;
  await registration.showNotification(payload.title, {
    body: payload.body,
    icon: '/pwa-192x192.png',
    badge: '/pwa-192x192.png',
    tag: payload.tag || 'mytab-local',
    renotify: true,
    data: { url: payload.url || '/?view=chiusure' },
  });
  return true;
}

export function markAcquisitionDraftsSeen(draftIds = null) {
  const payload = draftIds?.length ? { draft_ids: draftIds } : {};
  return apiFetch('/api/acquisition-drafts/mark-seen/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {});
}
