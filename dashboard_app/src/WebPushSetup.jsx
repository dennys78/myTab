import { useEffect, useRef, useCallback } from 'react';
import { isWebPushSupported, subscribeWebPush, waitForServiceWorker } from './webPush';
import { isIOS, isStandalonePwa } from './pwaPlatform';

const SYNC_MIN_MS = 30_000;

export default function WebPushSetup({ enabled }) {
  const lastSyncRef = useRef(0);

  const syncPush = useCallback(async (force = false) => {
    if (!enabled || !isWebPushSupported()) return;
    if (isIOS() && !isStandalonePwa()) return;
    const now = Date.now();
    if (!force && now - lastSyncRef.current < SYNC_MIN_MS) return;
    lastSyncRef.current = now;

    await waitForServiceWorker();
    if (Notification.permission === 'granted') {
      await subscribeWebPush({ requestPermission: false }).catch(() => {});
    } else if (Notification.permission === 'default' && !isIOS()) {
      await subscribeWebPush({ requestPermission: true }).catch(() => {});
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;

    syncPush(true);
    const onVisible = () => {
      if (document.visibilityState === 'visible') syncPush(false);
    };
    const onFocus = () => syncPush(false);

    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onFocus);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onFocus);
    };
  }, [enabled, syncPush]);

  return null;
}
