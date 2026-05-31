import { apiFetch } from './api';

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

export async function subscribeWebPush({ requestPermission = true } = {}) {
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
    return { ok: false, reason: 'config' };
  }

  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyData.data.public_key),
    });
  }

  const saveRes = await apiFetch('/api/push/subscribe/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscription.toJSON()),
  });
  const saveData = await saveRes.json();
  if (saveData.status !== 'success') {
    return { ok: false, reason: 'save' };
  }

  return { ok: true };
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
