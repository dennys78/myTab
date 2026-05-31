import { useEffect, useRef } from 'react';
import { isWebPushSupported, subscribeWebPush, waitForServiceWorker } from './webPush';

export default function WebPushSetup({ enabled }) {
  const startedRef = useRef(false);

  useEffect(() => {
    if (!enabled || startedRef.current || !isWebPushSupported()) return;
    startedRef.current = true;

    (async () => {
      await waitForServiceWorker();
      if (Notification.permission === 'granted') {
        await subscribeWebPush({ requestPermission: false }).catch(() => {});
        return;
      }
      if (Notification.permission === 'denied') return;
      await subscribeWebPush({ requestPermission: true }).catch(() => {});
    })();
  }, [enabled]);

  return null;
}
