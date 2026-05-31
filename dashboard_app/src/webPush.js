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
    && 'Notification' in window
    && 'serviceWorker' in navigator
    && 'PushManager' in window
  );
}

export async function subscribeWebPush() {
  if (!isWebPushSupported()) {
    return { ok: false, reason: 'unsupported' };
  }

  let permission = Notification.permission;
  if (permission === 'default') {
    permission = await Notification.requestPermission();
  }
  if (permission !== 'granted') {
    return { ok: false, reason: 'denied' };
  }

  const keyRes = await apiFetch('/api/push/vapid-public-key/');
  const keyData = await keyRes.json();
  if (keyData.status !== 'success' || !keyData.data?.public_key) {
    return { ok: false, reason: 'config' };
  }

  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyData.data.public_key),
    });
  }

  const body = subscription.toJSON();
  const saveRes = await apiFetch('/api/push/subscribe/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const saveData = await saveRes.json();
  if (saveData.status !== 'success') {
    return { ok: false, reason: 'save' };
  }

  return { ok: true };
}

export function markAcquisitionDraftsSeen(draftIds = null) {
  const payload = draftIds?.length ? { draft_ids: draftIds } : {};
  return apiFetch('/api/acquisition-drafts/mark-seen/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {});
}
