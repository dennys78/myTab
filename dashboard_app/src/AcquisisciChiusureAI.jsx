import { useState, useEffect, useRef } from 'react';
import { Save, Loader2, X, Plus, Sparkles, Calculator, Camera, Images, Trash2 } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import {
  ACQUISITION_MODE_FIVE,
  ACQUISITION_MODE_TWO,
  isValidFiveModeFileCount,
  maxFilesForAcquisitionMode,
} from './acquisitionConfig';
import { ensurePushSubscription, markAcquisitionDraftsSeen, showLocalPushNotification } from './webPush';
import { buildClosureSavedMessage, buildClosureSavedNotificationPayload } from './closureNotifyUtils';
import AcquisitionProgressBar from './AcquisitionProgressBar';
import {
  createAcquisitionProgressController,
  postExtractAiWithProgress,
} from './acquisitionProgress';
import { useCompactCaptureUI } from './useCompactCaptureUI';

function useIsMobile() {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 1024px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)');
    const h = (e) => setMobile(e.matches);
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, []);
  return mobile;
}

export default function AcquisisciChiusureAI({ onBack }) {
  const isMobile = useIsMobile();
  const compactCaptureUI = useCompactCaptureUI();
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const filesRef = useRef([]);
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [loadingDraftId, setLoadingDraftId] = useState(null);
  const [deletingDraftId, setDeletingDraftId] = useState(null);
  const [previewEditable, setPreviewEditable] = useState(false);
  const [reextracting, setReextracting] = useState(false);
  const [aiProvider, setAiProvider] = useState('groq');
  const [acquisitionFileMode, setAcquisitionFileMode] = useState(ACQUISITION_MODE_FIVE);
  const maxAcquisitionFiles = maxFilesForAcquisitionMode(acquisitionFileMode);
  const isFiveFileMode = acquisitionFileMode === ACQUISITION_MODE_FIVE;
  const loadDraftAbortRef = useRef(null);
  const loadDraftRequestIdRef = useRef(0);
  const progressControllerRef = useRef(null);
  const [extractProgress, setExtractProgress] = useState(null);

  const fetchDrafts = () => {
    apiFetch('/api/acquisition-drafts/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') setDrafts(d.data);
      })
      .catch(() => {});
  };

  useEffect(() => { fetchDrafts(); }, []);

  useEffect(() => {
    markAcquisitionDraftsSeen();
    ensurePushSubscription({ requestPermission: false }).catch(() => {});
  }, []);

  useEffect(() => () => {
    loadDraftAbortRef.current?.abort();
    progressControllerRef.current?.cancel();
  }, []);

  useEffect(() => {
    apiFetch('/api/acquisition/ai-provider/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setAiProvider(d.data.provider || 'groq');
          const mode = d.data.ai_acquisition_file_mode || ACQUISITION_MODE_FIVE;
          setAcquisitionFileMode(mode);
        }
      })
      .catch(() => {});
  }, [user?.active_company_id]);

  useEffect(() => {
    if (filesRef.current.length <= maxAcquisitionFiles) return;
    const trimmed = filesRef.current.slice(0, maxAcquisitionFiles);
    filesRef.current = trimmed;
    setFiles([...trimmed]);
  }, [maxAcquisitionFiles]);

  const providerLabel = aiProvider === 'gemini' ? 'Gemini' : 'Groq';

  // Rigenera thumbnail ogni volta che cambia la lista file
  useEffect(() => {
    const urls = filesRef.current.map(f => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach(u => URL.revokeObjectURL(u));
  }, [files]);

  const addFiles = (e) => {
    if (!e.target.files?.length) return;
    const remaining = maxAcquisitionFiles - filesRef.current.length;
    if (remaining <= 0) return;
    const incoming = Array.from(e.target.files).slice(0, remaining);
    // Usa ref per evitare qualsiasi problema di closure stale su iOS
    const next = [...filesRef.current, ...incoming].slice(0, maxAcquisitionFiles);
    filesRef.current = next;
    setFiles([...next]);
    e.target.value = '';          // permette di ri-selezionare lo stesso file
  };

  const removeFile = (index) => {
    const next = filesRef.current.filter((_, i) => i !== index);
    filesRef.current = next;
    setFiles([...next]);
  };

  const openCamera = () => {
    if (filesRef.current.length >= maxAcquisitionFiles) return;
    cameraInputRef.current?.click();
  };

  const openGallery = () => {
    if (filesRef.current.length >= maxAcquisitionFiles) return;
    galleryInputRef.current?.click();
  };

  const stopProgress = (success = true) => {
    if (success) {
      progressControllerRef.current?.complete();
    } else {
      progressControllerRef.current?.cancel();
    }
    progressControllerRef.current = null;
  };

  const handleExtract = () => {
    if (!filesRef.current.length) return;
    if (isFiveFileMode && !isValidFiveModeFileCount(filesRef.current.length)) {
      setError('Carica 5 immagini (standard) oppure 6 con il report Mooney aggiuntivo.');
      return;
    }
    const imageCount = filesRef.current.length;
    const controller = createAcquisitionProgressController(imageCount, setExtractProgress, {
      twoFileMode: acquisitionFileMode === ACQUISITION_MODE_TWO,
    });
    progressControllerRef.current = controller;
    controller.start();
    setLoading(true);
    setError(null);

    const fd = new FormData();
    filesRef.current.forEach((f, i) => fd.append(`file${i}`, f));

    postExtractAiWithProgress(fd, {
      onUploadProgress: (ratio) => controller.setUploadProgress(ratio),
    })
      .then((d) => {
        if (d?.status === 'success' && d.data) {
          try {
            applyPreviewData(d.data);
            stopProgress(true);
          } catch (err) {
            setError(err?.message || 'Errore elaborazione dati estratti.');
            stopProgress(false);
          }
        } else {
          setError(d?.error || d?.message || 'Errore durante l\'estrazione.');
          stopProgress(false);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Errore di rete.');
        }
        stopProgress(false);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const applyPreviewData = (data, { cached = false } = {}) => {
    const items = Array.isArray(data?.items) ? data.items : [];
    const enriched = {
      ...data,
      summary: { ...(data?.summary || {}) },
      items: items.map((item, i) => ({ ...item, id: item.id || `p${i}_${Date.now()}` })),
      extract_cached: cached,
    };
    if (!enriched.date) enriched.date = new Date().toISOString().split('T')[0];
    setPreviewEditable(!isMobile);
    setPreviewData(enriched);
    setError(null);
  };

  const loadDraft = (draftId, { force = false } = {}) => {
    loadDraftAbortRef.current?.abort();
    progressControllerRef.current?.cancel();
    const controller = new AbortController();
    loadDraftAbortRef.current = controller;
    const requestId = ++loadDraftRequestIdRef.current;

    const draftMeta = drafts.find((item) => item.id === draftId);
    const imageCount = draftMeta?.photo_count || 1;
    const progress = createAcquisitionProgressController(imageCount, setExtractProgress, {
      skipUpload: true,
      twoFileMode: acquisitionFileMode === ACQUISITION_MODE_TWO,
    });
    progressControllerRef.current = progress;
    progress.start();

    setLoadingDraftId(draftId);
    setError(null);
    if (force) setReextracting(true);

    apiFetch(`/api/acquisition-drafts/${draftId}/extract-ai/`, {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force }),
    })
      .then(r => r.json())
      .then(d => {
        if (requestId !== loadDraftRequestIdRef.current) return;
        if (d.status === 'success' && d.data) {
          applyPreviewData(d.data, { cached: !!d.cached });
          stopProgress(true);
        } else {
          setError(d.error || 'Errore durante il caricamento della bozza.');
          stopProgress(false);
        }
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setError('Errore di rete.');
        stopProgress(false);
      })
      .finally(() => {
        if (requestId !== loadDraftRequestIdRef.current) return;
        setLoadingDraftId(null);
        setReextracting(false);
        loadDraftAbortRef.current = null;
      });
  };

  const removeDraft = (draft) => {
    if (!window.confirm(`Rimuovere la bozza di ${draft.operator || 'Telegram'}? L'incasso non verrà registrato.`)) return;
    setDeletingDraftId(draft.id);
    setError(null);
    apiFetch(`/api/acquisition-drafts/${draft.id}/cancel/`, { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setDrafts(prev => prev.filter(item => item.id !== draft.id));
        } else {
          setError(d.error || 'Errore durante la rimozione della bozza.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setDeletingDraftId(null));
  };

  const calcItemSaldo = (item) => Math.round(((Number(item.entrate) || 0) - Math.abs(Number(item.uscite) || 0)) * 100) / 100;

  const handleItemChange = (id, field, value) => {
    setPreviewData(prev => {
      const items = prev.items.map(item => {
        if (item.id !== id) return item;
        const upd = { ...item, [field]: field === 'descrizione' ? value.toUpperCase() : (parseFloat(value) || 0) };
        if (field === 'uscite') upd.uscite = Math.abs(upd.uscite);
        if (field === 'entrate' || field === 'uscite') upd.saldo = calcItemSaldo(upd);
        return upd;
      });
      return {
        ...prev,
        items,
        summary: { ...prev.summary, differenza: calcDifferenza(prev.summary, items, prev.with_reports) },
      };
    });
  };

  const calcSaldoReparti = (items) =>
    Math.round((items || []).reduce((sum, item) => sum + calcItemSaldo(item), 0) * 100) / 100;

  // Con i report giochi (5 foto): Differenza = Totale riportato da cassa - Somma algebrica saldi reparti
  const calcDifferenzaReparti = (s, items) =>
    Math.round(((s.totale || 0) - calcSaldoReparti(items)) * 100) / 100;

  // Solo foglio incasso (2 foto): vecchio calcolo basato sul totale scassettato
  const calcDifferenzaCassetto = (s) => {
    const atteso = (s.totale || 0) - (s.pag_pos || 0) - (s.distrib || 0) - (s.reso_auto || 0) - (s.reso_cont || 0);
    return Math.round(((s.totale_cassetto || 0) - atteso) * 100) / 100;
  };

  const calcDifferenza = (s, items, withReports) =>
    withReports ? calcDifferenzaReparti(s, items) : calcDifferenzaCassetto(s);

  const handleSummaryChange = (e) => {
    const { name, value } = e.target;
    setPreviewData(prev => {
      const updated = { ...prev.summary, [name]: parseFloat(value) || 0 };
      updated.differenza = calcDifferenza(updated, prev.items, prev.with_reports);
      return { ...prev, summary: updated };
    });
  };

  const addItem = () => setPreviewData(prev => {
    const items = [...prev.items, { id: `n${Date.now()}`, descrizione: '', entrate: 0, uscite: 0, saldo: 0 }];
    return { ...prev, items, summary: { ...prev.summary, differenza: calcDifferenza(prev.summary, items, prev.with_reports) } };
  });

  const removeItem = (id) => setPreviewData(prev => {
    const items = prev.items.filter(i => i.id !== id);
    return { ...prev, items, summary: { ...prev.summary, differenza: calcDifferenza(prev.summary, items, prev.with_reports) } };
  });

  const handleAcquire = async () => {
    const cleanItems = previewData.items.map(item => {
      const cleanItem = { ...item, uscite: Math.abs(Number(item.uscite) || 0), saldo: calcItemSaldo(item) };
      delete cleanItem.id;
      return cleanItem;
    });
    const withReports = !!previewData.with_reports;
    const summaryPayload = {
      ...previewData.summary,
      totale_cassetto: withReports ? 0 : (previewData.summary.totale_cassetto || 0),
      differenza: calcDifferenza(previewData.summary, previewData.items, withReports),
    };
    setSaving(true);
    setError(null);
    await ensurePushSubscription({ requestPermission: true, forceRenew: true }).catch(() => {});

    apiFetch('/api/closures/insert/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: previewData.date,
        operator: user?.username || 'IA Groq',
        summary: summaryPayload,
        items: cleanItems,
        draft_id: previewData.draft_id,
      }),
    })
      .then(async (r) => {
        const d = await r.json().catch(() => ({}));
        if (!r.ok && d.status !== 'success' && !d.id) {
          setError(d.error || `Errore salvataggio (${r.status}).`);
          return;
        }
        if (d.status === 'success' || d.id) {
          const devices = d.push_devices ?? 0;
          const sent = d.push_sent ?? 0;
          const confirmationMessage = d.confirmation_message
            || buildClosureSavedMessage({
              date: previewData.date,
              operator: user?.username,
              items: previewData.items,
              summary: summaryPayload,
              saldoCassa: d.saldo_cassa ?? 0,
              fondoCassa: d.fondo_cassa ?? 0,
            });
          let shown = false;
          if (sent === 0) {
            shown = await showLocalPushNotification(
              buildClosureSavedNotificationPayload({
                date: previewData.date,
                operator: user?.username,
                items: previewData.items,
                summary: summaryPayload,
                saldoCassa: d.saldo_cassa ?? 0,
                fondoCassa: d.fondo_cassa ?? 0,
              }),
            ).catch(() => false);
          }
          let alertMessage = confirmationMessage;
          if (!shown && sent === 0) {
            alertMessage += '\n\nNessuna notifica push inviata. Vai in Impostazioni → Notifiche browser '
              + 'e premi "Registra questo smartphone" su ogni telefono.';
          } else if (sent > 0) {
            alertMessage += `\n\nRiepilogo inviato a ${sent} dispositivo${sent === 1 ? '' : 'i'}`
              + (devices > sent ? ` (registrati in azienda: ${devices})` : '')
              + '. Riceverai anche Telegram se il bot è attivo.';
          }
          alert(alertMessage);
          fetchDrafts();
          onBack();
        } else {
          setError(d.error || 'Errore salvataggio.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const inp = (extra = {}) => ({
    padding: '0.5rem 0.6rem',
    background: 'var(--bg-dark)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '6px',
    fontSize: '0.9rem',
    ...extra,
  });

  const numInp = (extra = {}) => inp({
    inputMode: 'decimal',
    ...extra,
  });

  const fieldsLocked = isMobile && !previewEditable;
  const summaryEditable = true;

  const summaryLabel = (key) => ({
    totale: 'Totale riportato da cassa',
    totale_cassetto: 'Totale scassettato',
    differenza: 'Differenza',
  }[key] || key.replace(/_/g, ' '));

  // ─── PREVIEW ────────────────────────────────────────────────────────────────
  if (previewData) {
    const regularSummaryEntries = Object.entries(previewData.summary).filter(
      ([key]) => !['totale_cassetto', 'differenza'].includes(key)
    );
    const withReports = !!previewData.with_reports;
    const saldoTotaleReparti = previewData.items.reduce((sum, item) => sum + calcItemSaldo(item), 0);
    const totaleScassettato = previewData.summary.totale_cassetto ?? 0;
    const differenza = calcDifferenza(previewData.summary, previewData.items, withReports);
    const previewImages = previewData.images?.length
      ? previewData.images
      : previews.map((url, index) => ({ id: `local_${index}`, url }));

    return (
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>

        {(extractProgress || reextracting) && (
          <div style={{ marginBottom: '1rem' }}>
            <AcquisitionProgressBar
              progress={extractProgress || {
                active: true,
                percent: 8,
                message: 'Decodifica immagini in corso…',
              }}
            />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h1 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: isMobile ? '1.2rem' : '1.75rem' }}>
              <Sparkles size={isMobile ? 20 : 24} color="var(--accent)" />
              Anteprima Estrazione IA
            </h1>
            {previewData.extract_cached && (
              <p style={{ margin: '0.35rem 0 0', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                Estrazione già memorizzata — stessi dati su PC e smartphone.
              </p>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {isMobile && !previewEditable && (
              <button
                onClick={() => setPreviewEditable(true)}
                style={{ padding: '0.5rem 1rem', background: 'rgba(59,130,246,0.12)', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: '6px', cursor: 'pointer', whiteSpace: 'nowrap', fontWeight: 600 }}
              >
                Modifica valori
              </button>
            )}
            {previewData.draft_id && (
              <button
                onClick={() => loadDraft(previewData.draft_id, { force: true })}
                disabled={reextracting || loadingDraftId === previewData.draft_id}
                style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '6px', cursor: 'pointer', whiteSpace: 'nowrap' }}
              >
                {reextracting ? 'Riesecuzione...' : 'Riesegui IA'}
              </button>
            )}
            <button
              onClick={() => { setPreviewData(null); setPreviewEditable(false); }}
              style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-main)', borderRadius: '6px', cursor: 'pointer', whiteSpace: 'nowrap' }}
            >
              ← Indietro
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.75rem 1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: isMobile ? '1rem' : '1.5rem', marginBottom: '1.5rem' }}>
          <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
            <Calculator size={18} color="var(--accent)" /> Dati Generali
          </h2>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Data Chiusura</label>
            <input type="date" value={previewData.date}
              onChange={e => setPreviewData(p => ({ ...p, date: e.target.value }))}
              style={{ ...inp(), width: isMobile ? '100%' : '200px' }} />
          </div>
          <div className="acq-summary-grid">
            {regularSummaryEntries.map(([key, val]) => {
              return (
                <div key={key}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem', textTransform: 'capitalize' }}>
                    {summaryLabel(key)}
                  </label>
                  <input type="number" name={key}
                    value={val === 0 ? '' : val}
                    onChange={handleSummaryChange} placeholder="0.00"
                    readOnly={!summaryEditable}
                    className={summaryEditable ? 'acq-edit-input' : 'acq-readonly-input'}
                    style={{ ...numInp(), width: '100%' }} />
                </div>
              );
            })}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',
            gap: '1rem',
            padding: '1rem',
            border: '1px solid var(--border-strong)',
            borderRadius: '14px',
            background: 'rgba(79, 141, 247, 0.08)',
          }}>
            {withReports ? (
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Somma algebrica saldi reparti
                </label>
                <div style={{
                  padding: '0.62rem 0.75rem',
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '1.1rem',
                  border: '1px solid var(--border-strong)',
                  background: 'var(--bg-dark)',
                  color: 'var(--text-main)',
                }}>
                  {saldoTotaleReparti.toFixed(2)}
                </div>
              </div>
            ) : (
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Totale scassettato
                </label>
                <input
                  type="number"
                  name="totale_cassetto"
                  value={totaleScassettato === 0 ? '' : totaleScassettato}
                  onChange={handleSummaryChange}
                  placeholder="0.00"
                  readOnly={!summaryEditable}
                  className={summaryEditable ? 'acq-edit-input' : 'acq-readonly-input'}
                  style={{ ...numInp({ width: '100%', fontSize: '1.1rem', fontWeight: 700, borderColor: 'var(--accent)' }) }}
                />
              </div>
            )}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Differenza
              </label>
              <div style={{
                padding: '0.62rem 0.75rem',
                borderRadius: '10px',
                fontWeight: 800,
                fontSize: '1.1rem',
                border: '1px solid var(--border-strong)',
                background: 'var(--bg-dark)',
                color: differenza > 0 ? 'var(--success)' : differenza < 0 ? 'var(--danger)' : 'var(--text-muted)',
              }}>
                {differenza >= 0 ? '+' : ''}{Number(differenza).toFixed(2)}
              </div>
            </div>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', margin: '0.6rem 0 0' }}>
            {withReports
              ? 'Differenza = Totale riportato da cassa − Somma algebrica saldi reparti'
              : 'Modifica i valori del riepilogo e il totale scassettato: la differenza si ricalcola automaticamente.'}
          </p>
        </div>

        {previewImages.length > 0 && (
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: isMobile ? '1rem' : '1.5rem', marginBottom: '1.5rem' }}>
            <h2 style={{ margin: '0 0 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
              <Images size={18} color="var(--accent)" /> Foto importazione
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.9rem' }}>
              {previewImages.map((image, index) => (
                <a key={image.id} href={image.url} target="_blank" rel="noreferrer" style={{ display: 'block', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden', background: 'var(--bg-dark)', textDecoration: 'none' }}>
                  <img
                    src={image.url}
                    alt={`Foto importazione ${index + 1}`}
                    style={{ width: '100%', height: isMobile ? '180px' : '150px', objectFit: 'cover', display: 'block' }}
                  />
                  <div style={{ padding: '0.55rem 0.7rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Foto {index + 1}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: isMobile ? '1rem' : '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1rem' }}>Voci di Reparto</h2>
            {!fieldsLocked && (
              <button onClick={addItem}
                style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.4rem 0.8rem', background: 'rgba(59,130,246,0.1)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
                <Plus size={15} /> Aggiungi
              </button>
            )}
          </div>

          <div className="table-responsive-wrapper">
            <table className="acq-items-table">
              <thead>
                <tr>
                  <th>Descrizione</th>
                  <th>Entrate</th>
                  <th>Uscite</th>
                  <th>Saldo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {previewData.items.length === 0 && (
                  <tr><td colSpan="5" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>Nessuna voce. Clicca Aggiungi.</td></tr>
                )}
                {previewData.items.map(item => (
                  <tr key={item.id}>
                    <td>
                      <input className={fieldsLocked ? 'acq-readonly-input' : 'acq-edit-input'} type="text" value={item.descrizione}
                        onChange={e => handleItemChange(item.id, 'descrizione', e.target.value)}
                        readOnly={fieldsLocked}
                        placeholder="Nome Reparto"
                        style={{ ...inp({ width: '100%', minWidth: isMobile ? '110px' : '150px' }) }} />
                    </td>
                    <td>
                      <input className={fieldsLocked ? 'acq-readonly-input' : 'acq-edit-input'} type="number" value={item.entrate === 0 ? '' : item.entrate}
                        onChange={e => handleItemChange(item.id, 'entrate', e.target.value)}
                        readOnly={fieldsLocked}
                        placeholder="0.00"
                        style={{ ...numInp({ width: isMobile ? '75px' : '95px' }) }} />
                    </td>
                    <td>
                      <input className={fieldsLocked ? 'acq-readonly-input' : 'acq-edit-input'} type="number" value={item.uscite === 0 ? '' : item.uscite}
                        onChange={e => handleItemChange(item.id, 'uscite', e.target.value)}
                        readOnly={fieldsLocked}
                        placeholder="0.00"
                        style={{ ...numInp({ width: isMobile ? '75px' : '95px' }) }} />
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-block', minWidth: isMobile ? '60px' : '80px',
                        padding: '0.5rem 0.4rem', fontWeight: '600', fontSize: '0.9rem',
                        color: calcItemSaldo(item) > 0 ? '#22c55e' : calcItemSaldo(item) < 0 ? 'var(--danger)' : 'var(--text-muted)',
                      }}>
                        {calcItemSaldo(item).toFixed(2)}
                      </span>
                    </td>
                    <td>
                      {!fieldsLocked && (
                        <button onClick={() => removeItem(item.id)}
                          style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.4rem' }}>
                          <X size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {previewData.items.length > 0 && (
                  <tr className="acq-total-row">
                    <td colSpan="3">Somma algebrica saldi reparti</td>
                    <td>
                      <span className={saldoTotaleReparti > 0 ? 'success' : saldoTotaleReparti < 0 ? 'danger' : ''}>
                        {saldoTotaleReparti.toFixed(2)}
                      </span>
                    </td>
                    <td></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="acq-actions">
          <button onClick={onBack}
            style={{ padding: '0.85rem 1.5rem', background: 'transparent', border: '1px solid var(--border)', color: 'white', borderRadius: '8px', cursor: 'pointer' }}>
            Annulla
          </button>
          <button onClick={handleAcquire} disabled={saving}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.85rem 1.5rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
            {saving ? <Loader2 size={20} className="spin" /> : <Save size={20} />}
            {saving ? 'Acquisizione...' : 'Acquisisci e Salva'}
          </button>
        </div>
      </div>
    );
  }

  // ─── UPLOAD ─────────────────────────────────────────────────────────────────
  const atLimit = files.length >= maxAcquisitionFiles;
  const canExtract = files.length > 0 && (!isFiveFileMode || isValidFiveModeFileCount(files.length));

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <Sparkles size={26} color="var(--accent)" /> Acquisisci con IA
      </h1>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', marginBottom: '0.4rem', fontSize: '0.9rem' }}>
        {isFiveFileMode
          ? 'Carica 5 o 6 immagini: riepilogo cassa e report giochi (6ª foto = Mooney opzionale).'
          : 'Carica 1 o 2 immagini del riepilogo chiusura cassa (foglio incasso).'}
      </p>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.78rem', marginBottom: '0.4rem', lineHeight: 1.45 }}>
        {isFiveFileMode
          ? 'Report Lottomatica e Sisal: entrate e uscite sostituite dai documenti dedicati. Con 6 foto anche Mooney. L\'ordine viene riconosciuto automaticamente.'
          : 'Il protocollo a 2 file estrae reparti e totali dal foglio incasso senza i report giochi separati.'}
      </p>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.78rem', marginBottom: '1.5rem' }}>
        Modello attivo: <strong style={{ color: 'var(--text-main)' }}>{providerLabel}</strong>
        {' '}— modificalo in <strong style={{ color: 'var(--text-main)' }}>Impostazioni</strong>
      </p>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.9rem 1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          {error}
        </div>
      )}

      {drafts.length > 0 && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '1rem', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Bozze ricevute da Telegram</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {drafts.map(draft => (
              <div key={draft.id} style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr auto', alignItems: 'center', gap: '0.75rem', padding: '0.75rem', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '10px' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, marginBottom: '0.15rem' }}>
                    {draft.operator || 'Telegram'} · {draft.photo_count} foto
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                    {Number(draft.pag_pos_reale) > 0 && (
                      <>POS reale € {Number(draft.pag_pos_reale).toFixed(2)} · </>
                    )}
                    Scassettato € {Number(draft.totale_scassettato).toFixed(2)} · {new Date(draft.created_at).toLocaleString('it-IT')}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'nowrap', justifyContent: isMobile ? 'flex-start' : 'flex-end', whiteSpace: 'nowrap' }}>
                  <button
                    onClick={() => loadDraft(draft.id)}
                    disabled={loadingDraftId !== null || deletingDraftId !== null}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 0.9rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 700 }}
                  >
                    {loadingDraftId === draft.id ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                    Carica bozza
                  </button>
                  <button
                    onClick={() => removeDraft(draft)}
                    disabled={loadingDraftId !== null || deletingDraftId !== null}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.55rem 0.8rem', background: 'transparent', color: 'var(--danger)', border: '1px solid var(--danger)', borderRadius: '8px', cursor: 'pointer', fontWeight: 700 }}
                  >
                    {deletingDraftId === draft.id ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />}
                    Rimuovi
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload area — tablet/touch: fotocamera + galleria; desktop: sfoglia file */}
      {compactCaptureUI ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture
            onChange={addFiles}
            style={{ display: 'none' }}
            aria-hidden
          />
          <button
            type="button"
            onClick={openCamera}
            disabled={atLimit}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem',
              width: '100%',
              padding: '1.25rem',
              background: atLimit ? 'var(--bg-card)' : 'var(--accent)',
              color: atLimit ? 'var(--text-muted)' : 'white',
              border: atLimit ? '1px solid var(--border)' : 'none',
              borderRadius: '12px',
              cursor: atLimit ? 'not-allowed' : 'pointer',
              fontSize: '1.1rem', fontWeight: '600',
            }}
          >
            <Camera size={26} /> Scatta foto
          </button>

          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={addFiles}
            style={{ display: 'none' }}
            aria-hidden
          />
          <button
            type="button"
            onClick={openGallery}
            disabled={atLimit}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem',
              width: '100%',
              padding: '1.25rem',
              background: 'var(--bg-card)',
              color: atLimit ? 'var(--text-muted)' : 'var(--text-main)',
              border: `1px solid ${atLimit ? 'var(--border)' : 'var(--accent)'}`,
              borderRadius: '12px',
              cursor: atLimit ? 'not-allowed' : 'pointer',
              fontSize: '1.1rem', fontWeight: '600',
            }}
          >
            <Images size={26} /> Dalla galleria
          </button>

          {atLimit && (
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Hai raggiunto il limite di {maxAcquisitionFiles} foto. Premi <strong style={{ color: 'white' }}>Avvio estrazione dati</strong> per procedere oppure rimuovi una foto per aggiungerne un&apos;altra.
            </p>
          )}
        </div>
      ) : (
        /* ── DESKTOP: area dashed classica ── */
        <div style={{ border: '2px dashed var(--border)', borderRadius: '12px', padding: '3rem 2rem', background: 'rgba(255,255,255,0.02)', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <Sparkles size={48} color="var(--accent)" />
          <h3 style={{ margin: 0 }}>Seleziona Immagini</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0 }}>PNG, JPG o JPEG — Max {maxAcquisitionFiles} file</p>
          <input type="file" id="ai-file-desktop" multiple accept="image/*" onChange={addFiles} style={{ display: 'none' }} />
          <label htmlFor="ai-file-desktop" style={{
            padding: '0.75rem 1.5rem',
            background: atLimit ? 'var(--bg-dark)' : 'var(--bg-card)',
            border: '1px solid var(--border)',
            color: atLimit ? 'var(--text-muted)' : 'white',
            borderRadius: '8px',
            cursor: atLimit ? 'not-allowed' : 'pointer',
            marginTop: '0.5rem',
            pointerEvents: atLimit ? 'none' : 'auto',
          }}>
            {atLimit ? `Limite ${maxAcquisitionFiles} file raggiunto` : 'Sfoglia File'}
          </label>
        </div>
      )}

      {/* Anteprima foto accumulate */}
      {files.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            {files.length}/{maxAcquisitionFiles} {files.length === 1 ? 'foto selezionata' : 'foto selezionate'}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {files.map((file, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--bg-card)', padding: '0.6rem 0.75rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
                {/* Thumbnail */}
                {previews[i] && (
                  <img
                    src={previews[i]}
                    alt={`Foto ${i + 1}`}
                    style={{ width: '56px', height: '56px', objectFit: 'cover', borderRadius: '6px', flexShrink: 0 }}
                  />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Foto {i + 1}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {file.name}
                  </div>
                </div>
                <button onClick={() => removeFile(i)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', flexShrink: 0, padding: '0.25rem' }}>
                  <X size={18} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div style={{ marginBottom: '1rem' }}>
          <AcquisitionProgressBar
            progress={extractProgress || {
              active: true,
              percent: 2,
              message: 'Avvio estrazione dati',
            }}
          />
        </div>
      )}

      <button onClick={handleExtract} disabled={!canExtract || loading}
        style={{
          width: '100%', padding: '1rem',
          background: files.length && !loading ? 'var(--accent)' : 'var(--bg-card)',
          color: files.length && !loading ? 'white' : 'var(--text-muted)',
          border: 'none', borderRadius: '10px', fontSize: '1rem', fontWeight: 'bold',
          cursor: files.length && !loading ? 'pointer' : 'not-allowed',
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem',
          minHeight: '54px',
          opacity: loading ? 0.7 : 1,
        }}>
        <Sparkles size={20} /> Avvio estrazione dati
      </button>
    </div>
  );
}
