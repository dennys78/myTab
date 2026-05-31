import { useEffect, useRef } from 'react';
import { isWebPushSupported, subscribeWebPush } from './webPush';

const SESSION_KEY = 'mytab_push_prompted';

export default function WebPushSetup({ enabled }) {
  const startedRef = useRef(false);

  useEffect(() => {
    if (!enabled || startedRef.current || !isWebPushSupported()) return;
    startedRef.current = true;

    if (Notification.permission === 'granted') {
      subscribeWebPush().catch(() => {});
      return;
    }

    if (Notification.permission === 'denied') return;
    if (sessionStorage.getItem(SESSION_KEY)) return;

    sessionStorage.setItem(SESSION_KEY, '1');
    subscribeWebPush().catch(() => {});
  }, [enabled]);

  return null;
}
