/** Fasi stimate durante upload + estrazione IA (allineate al backend). */

export function buildAcquisitionProgressSteps(imageCount, { skipUpload = false, twoFileMode = false, positionalSlots = false } = {}) {
  const n = Math.max(1, Number(imageCount) || 1);
  const steps = [];

  if (!skipUpload) {
    steps.push({ phase: 'upload', label: 'Caricamento immagini…', weight: 12 });
  }
  steps.push({ phase: 'queue', label: 'In coda per l\'analisi IA…', weight: 6 });
  steps.push({ phase: 'prep', label: 'Preparazione allegati…', weight: 6 });

  if (twoFileMode || positionalSlots) {
    steps.push({
      phase: 'decode',
      label: positionalSlots ? 'Assegnazione report per ordine foto…' : (n === 1 ? 'Analisi foto…' : `Analisi ${n} foto…`),
      weight: 10,
    });
  } else if (n >= 3) {
    for (let i = 1; i <= n; i += 1) {
      steps.push({
        phase: 'decode',
        label: `Classificazione foto ${i} di ${n}…`,
        weight: 22 / n,
      });
    }
  } else {
    steps.push({
      phase: 'decode',
      label: n === 1 ? 'Analisi foto…' : `Analisi ${n} foto…`,
      weight: 18,
    });
  }

  steps.push({ phase: 'closure', label: 'Estrazione chiusura cassa…', weight: twoFileMode ? 42 : 26 });
  if (!twoFileMode) {
    steps.push({ phase: 'reports', label: 'Lettura report reparti…', weight: positionalSlots ? 28 : 16 });
  }
  steps.push({ phase: 'finalize', label: 'Finalizzazione…', weight: 6 });
  return steps;
}

function labelForProgress(steps, ratio) {
  const target = Math.min(0.999, Math.max(0, ratio));
  const totalWeight = steps.reduce((sum, step) => sum + step.weight, 0);
  let acc = 0;
  for (const step of steps) {
    acc += step.weight / totalWeight;
    if (target <= acc) return step.label;
  }
  return steps[steps.length - 1]?.label || 'Elaborazione…';
}

/**
 * @param {number} imageCount
 * @param {(state: { percent: number, message: string, active: boolean } | null) => void} onUpdate
 * @param {{ skipUpload?: boolean, twoFileMode?: boolean }} options
 */
export function createAcquisitionProgressController(imageCount, onUpdate, options = {}) {
  const steps = buildAcquisitionProgressSteps(imageCount, options);
  const uploadCap = options.skipUpload ? 0 : 14;
  const simMax = 96;
  let cancelled = false;
  let timer = null;
  let uploadWatchdog = null;
  let uploadDone = false;
  let simStart = null;
  let simFrom = uploadCap;

  const clear = () => {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    if (uploadWatchdog) {
      clearTimeout(uploadWatchdog);
      uploadWatchdog = null;
    }
  };

  const simSteps = steps.filter((s) => s.phase !== 'upload');
  // Job asincrono: 5/6 file possono richiedere alcuni minuti
  const durationMs = Math.min(180_000, 8_000 + Math.max(1, imageCount) * 12_000);

  const startSimulation = (fromPercent) => {
    simFrom = fromPercent;
    simStart = Date.now();
    clear();
    timer = setInterval(() => {
      if (cancelled) return;
      const elapsed = Date.now() - simStart;
      const t = Math.min(1, elapsed / durationMs);
      const eased = 1 - (1 - t) ** 1.35;
      const percent = simFrom + eased * (simMax - simFrom);
      const ratio = uploadCap > 0
        ? (percent - uploadCap) / (simMax - uploadCap)
        : percent / simMax;
      onUpdate({
        percent: Math.round(percent),
        message: labelForProgress(simSteps, ratio),
        active: true,
      });
    }, 100);
  };

  return {
    start() {
      cancelled = false;
      uploadDone = false;
      if (options.skipUpload) {
        onUpdate({ percent: 4, message: simSteps[0]?.label || 'Elaborazione…', active: true });
        startSimulation(0);
      } else {
        onUpdate({ percent: 2, message: 'Avvio estrazione dati', active: true });
        uploadWatchdog = setTimeout(() => {
          if (!uploadDone && !cancelled && !timer) {
            startSimulation(uploadCap * 0.35);
          }
        }, 1200);
      }
    },
    setUploadProgress(ratio) {
      if (cancelled || options.skipUpload) return;
      const clamped = Math.min(1, Math.max(0, ratio));
      const percent = clamped * uploadCap;
      onUpdate({
        percent: Math.max(2, Math.round(percent)),
        message: 'Caricamento immagini…',
        active: true,
      });
      if (clamped >= 1) {
        uploadDone = true;
        if (uploadWatchdog) {
          clearTimeout(uploadWatchdog);
          uploadWatchdog = null;
        }
        if (!timer) startSimulation(uploadCap);
      }
    },
    setMessage(message) {
      if (cancelled) return;
      onUpdate({
        percent: Math.min(simMax, Math.max(uploadCap, 20)),
        message: message || 'Elaborazione in corso…',
        active: true,
      });
    },
    complete() {
      if (cancelled) return;
      cancelled = true;
      clear();
      onUpdate({ percent: 100, message: 'Completato', active: false });
      window.setTimeout(() => onUpdate(null), 450);
    },
    cancel() {
      cancelled = true;
      clear();
      onUpdate(null);
    },
  };
}

export function getCsrfToken() {
  const match = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='));
  return match ? decodeURIComponent(match.split('=')[1]) : '';
}

/**
 * Poll stato job estrazione fino a ready/error.
 * @returns {Promise<object>} risposta finale con data
 */
export async function pollDraftExtractStatus(draftId, { signal, onStatus, intervalMs = 1500, timeoutMs = 480_000 } = {}) {
  const started = Date.now();
  let lastStatus = '';

  while (true) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError');
    }
    if (Date.now() - started > timeoutMs) {
      throw new Error(
        'L\'analisi IA sta impiegando troppo tempo. Lascia aperta la pagina e riprova tra un minuto, oppure verifica le chiavi API in Impostazioni.',
      );
    }

    const res = await fetch(`/api/acquisition-drafts/${draftId}/extract-status/`, {
      method: 'GET',
      credentials: 'include',
      signal,
      headers: {
        Accept: 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
    });

    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(
        `Risposta non valida dal server (HTTP ${res.status || '?'}). Riprova tra poco.`,
      );
    }

    const extractStatus = data.extract_status || data.status || '';
    if (extractStatus !== lastStatus) {
      lastStatus = extractStatus;
      if (onStatus) onStatus(extractStatus, data);
    }

    if (extractStatus === 'ready' || data.status === 'success') {
      if (data.data) return data;
      throw new Error(data.error || 'Estrazione completata senza dati.');
    }

    if (extractStatus === 'error' || data.status === 'error') {
      throw new Error(
        data.error
          || 'Errore durante l\'analisi IA. Controlla le foto (2, 5 o 6 file) e riprova.',
      );
    }

    await new Promise((resolve) => {
      const t = setTimeout(resolve, intervalMs);
      if (signal) {
        signal.addEventListener('abort', () => {
          clearTimeout(t);
          resolve();
        }, { once: true });
      }
    });
  }
}

/** Upload con progresso reale + avvio job asincrono. */
export function postExtractAiWithProgress(formData, { onUploadProgress, signal } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/closures/extract-ai/');
    xhr.withCredentials = true;
    const csrf = getCsrfToken();
    if (csrf) xhr.setRequestHeader('X-CSRFToken', csrf);

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException('Aborted', 'AbortError'));
        return;
      }
      signal.addEventListener('abort', () => xhr.abort(), { once: true });
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onUploadProgress) {
        onUploadProgress(event.loaded / event.total);
      }
    };

    xhr.onload = () => {
      let data;
      try {
        data = JSON.parse(xhr.responseText || '{}');
      } catch {
        if (xhr.status === 504 || xhr.status === 502) {
          reject(
            new Error(
              'Timeout del server durante il caricamento. Riprova con meno foto oppure verifica la connessione.',
            ),
          );
          return;
        }
        reject(
          new Error(
            `Risposta non valida dal server (HTTP ${xhr.status || '?'}). Riprova tra poco.`,
          ),
        );
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        if (data.status === 'queued' || data.status === 'processing' || data.status === 'success' || data.data) {
          resolve(data);
          return;
        }
        reject(new Error(data.error || data.message || 'Errore estrazione.'));
        return;
      }
      reject(new Error(data.error || data.message || 'Errore estrazione.'));
    };

    xhr.onerror = () => reject(new Error('Errore di rete.'));
    xhr.onabort = () => reject(new DOMException('Aborted', 'AbortError'));
    xhr.send(formData);
  });
}
