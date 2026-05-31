import { useEffect, useState } from 'react';
import { Download, Share, X, Smartphone } from 'lucide-react';
import { isIOS, isStandalonePwa } from './pwaPlatform';

function isMobile() {
  return window.innerWidth < 900 || isIOS() || /Android/i.test(navigator.userAgent);
}

export default function InstallPwa() {
  const [visible, setVisible] = useState(false);
  const [ios, setIos] = useState(false);
  const [installPrompt, setInstallPrompt] = useState(null);

  useEffect(() => {
    if (isStandalonePwa() || sessionStorage.getItem('mytab-pwa-hint-dismissed') === '1') return;
    if (!isMobile()) return;

    setIos(isIOS());
    setVisible(true);

    const onBip = (e) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', onBip);
    return () => window.removeEventListener('beforeinstallprompt', onBip);
  }, []);

  const dismiss = () => {
    sessionStorage.setItem('mytab-pwa-hint-dismissed', '1');
    setVisible(false);
  };

  const installAndroid = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice;
    setInstallPrompt(null);
    dismiss();
  };

  if (!visible) return null;

  return (
    <div className="install-pwa-banner" role="region" aria-label="Installa myTab">
      <div className="install-pwa-icon-wrap">
        <img src="/apple-touch-icon.png" alt="" width={44} height={44} className="install-pwa-icon" />
      </div>
      <div className="install-pwa-body">
        <strong className="install-pwa-title">
          <Smartphone size={16} style={{ verticalAlign: '-2px', marginRight: '0.35rem' }} />
          Installa myTab sul telefono
        </strong>
        {ios ? (
          <p className="install-pwa-text">
            In <strong>Safari</strong>: tocca <Share size={14} style={{ verticalAlign: '-2px' }} /> Condividi
            → <strong>Aggiungi a Home</strong>. Poi apri myTab dall&apos;icona: le notifiche push
            funzionano solo dalla app installata (iOS 16.4+).
          </p>
        ) : installPrompt ? (
          <p className="install-pwa-text">
            Aggiungi myTab alla schermata Home per usarla come app, con icona dedicata.
          </p>
        ) : (
          <p className="install-pwa-text">
            Dal menu del browser (⋮) scegli <strong>Installa app</strong> o{' '}
            <strong>Aggiungi a schermata Home</strong>.
          </p>
        )}
        {!ios && installPrompt && (
          <button type="button" className="install-pwa-btn" onClick={installAndroid}>
            <Download size={16} /> Installa ora
          </button>
        )}
      </div>
      <button type="button" className="install-pwa-close" onClick={dismiss} aria-label="Chiudi">
        <X size={18} />
      </button>
    </div>
  );
}
