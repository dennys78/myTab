import { useEffect } from 'react';

function isMobileViewport() {
  return window.matchMedia('(max-width: 768px)').matches;
}

export function useLandscapeOnMobile(active) {
  useEffect(() => {
    if (!active || !isMobileViewport()) return undefined;

    document.documentElement.classList.add('prefer-landscape-active');

    const lock = async () => {
      try {
        if (screen.orientation?.lock) {
          await screen.orientation.lock('landscape');
        }
      } catch {
        /* Su iOS il lock può richiedere un gesto utente */
      }
    };
    lock();

    return () => {
      document.documentElement.classList.remove('prefer-landscape-active');
      try {
        screen.orientation?.unlock?.();
      } catch {
        /* ignore */
      }
    };
  }, [active]);
}
