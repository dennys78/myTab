const GIORNI = [5, 7, 10, 14];
const DEFAULT_SCORTA_PCT = 200;
const SCORTA_PCT_MIN = 10;
const SCORTA_PCT_MAX = 250;
const FAMIGLIE_TABACCHI = [
  'Sigarette',
  'Tabacco riscaldato',
  'Trinciati',
  'Sigari e sigaretti',
  'Altri tabacchi',
];
const FAMIGLIE = [
  ...FAMIGLIE_TABACCHI,
  'Dispositivi',
  'Solidi',
];

export const SEZIONI_ORDINE = [
  { id: 'tabacchi', label: 'Tabacchi', famiglie: FAMIGLIE_TABACCHI },
  { id: 'dispositivi', label: 'Dispositivi', famiglie: ['Dispositivi'] },
  { id: 'solidi', label: 'Solidi', famiglie: ['Solidi'] },
];

export function sezioneDiRiga(riga) {
  if (riga?.famiglia === 'Solidi') return 'solidi';
  if (riga?.famiglia === 'Dispositivi' || riga?.tipo === 'dispositivo') return 'dispositivi';
  return 'tabacchi';
}

export function righeSezione(righe, sezioneId) {
  return (righe || []).filter(riga => sezioneDiRiga(riga) === sezioneId);
}

export function normalizzaScortaPct(value, fallback = DEFAULT_SCORTA_PCT) {
  const pct = Number.parseInt(value, 10);
  if (!Number.isFinite(pct)) return fallback;
  return Math.max(SCORTA_PCT_MIN, Math.min(SCORTA_PCT_MAX, pct));
}

export function giorniAllaConsegna(oggi, ultimoChiuso, dataConsegna) {
  const inizio = oggi > ultimoChiuso ? oggi : addDays(ultimoChiuso, 1);
  return Math.max(0, diffDays(dataConsegna, inizio));
}

export function inizioVendite(oggi, ultimoChiuso) {
  return oggi > ultimoChiuso ? oggi : addDays(ultimoChiuso, 1);
}

export function prossimoGiornoConsegna(oggiIso, weekday = 0) {
  // weekday: 0=lunedì … 6=domenica (come Python date.weekday)
  const day = parseIso(oggiIso);
  const jsTarget = (((Number(weekday) % 7) + 7) % 7 + 1) % 7;
  let delta = (jsTarget - day.getDay() + 7) % 7;
  if (delta === 0) delta = 7;
  day.setDate(day.getDate() + delta);
  return isoLocale(day);
}

export function unitaOrdine(prezzo, prezzoKg, minimoGrammi) {
  const p = Number(prezzo) || 0;
  const pkg = Number(prezzoKg) || 0;
  const minimo = Number(minimoGrammi) || 0;
  if (p <= 0 || pkg <= 0 || minimo <= 0) return null;
  const u = Math.round((minimo * pkg) / (1000 * p));
  if (u <= 0) return null;
  return { pacchettiPerUnita: u, kgPerUnita: roundKg(minimo / 1000) };
}

export function propostaUnita(media, giacenza, pacchettiPerUnita, giorniCopertura, giorniAlla, scortaPct = DEFAULT_SCORTA_PCT) {
  const u = Number(pacchettiPerUnita) || 0;
  const fattore = normalizzaScortaPct(scortaPct) / 100;
  const alla = Math.max(0, Number(giacenza) - Number(media) * Number(giorniAlla));
  const target = Number(media) * Number(giorniCopertura) * fattore;
  const mancano = target - alla;
  const soglia = 0.25 * u;
  let unita = 0;
  if (u > 0 && mancano >= soglia - 1e-9) {
    unita = Math.ceil(Math.round((mancano / u) * 1e8) / 1e8 - 1e-9);
  }
  const giorniFine = Number(media) === 0
    ? null
    : Math.floor(Math.max(0, Number(giacenza)) / Number(media));
  return { allaConsegna: alla, unita, giorniFine };
}

export function urgenzaDataFine(giorniFine, giorniAlla, giorniCopertura) {
  if (giorniFine == null) return 'normale';
  if (giorniFine <= Number(giorniAlla)) return 'rossa';
  if (giorniFine < Number(giorniAlla) + Number(giorniCopertura) + 3) return 'arancione';
  return 'normale';
}

export function proiezioneDopoOrdine(
  media,
  giacenza,
  pacchettiPerUnita,
  unitaOrdinate,
  giorniAlla,
  giorniCopertura,
  dataConsegna,
) {
  const m = Number(media) || 0;
  const u = Number(pacchettiPerUnita) || 0;
  const pezziOrdine = Math.max(0, Number(unitaOrdinate) || 0) * u;
  const alla = Math.max(0, Number(giacenza) - m * Number(giorniAlla));
  const dopoConsegna = alla + pezziOrdine;
  const residuo = dopoConsegna - m * Number(giorniCopertura);
  if (m <= 0) {
    return {
      giacenzaDopoConsegna: dopoConsegna,
      residuoCopertura: residuo,
      giorniConOrdine: null,
      dataCopreFino: null,
      urgenzaCopertura: 'normale',
    };
  }
  const giorniConOrdine = Math.floor(dopoConsegna / m);
  const dataCopreFino = addDays(dataConsegna, giorniConOrdine);
  let urgenzaCopertura = 'normale';
  if (residuo < 0) urgenzaCopertura = 'rossa';
  else if (residuo < m * 3) urgenzaCopertura = 'arancione';
  return {
    giacenzaDopoConsegna: dopoConsegna,
    residuoCopertura: residuo,
    giorniConOrdine,
    dataCopreFino,
    urgenzaCopertura,
  };
}

export function ricalcolaRighe(righe, { giorniCopertura, oggi, ultimoChiuso, dataConsegna, scortaPct = DEFAULT_SCORTA_PCT }) {
  const distanza = giorniAllaConsegna(oggi, ultimoChiuso, dataConsegna);
  const inizio = inizioVendite(oggi, ultimoChiuso);
  const pct = normalizzaScortaPct(scortaPct);
  return righe.map(riga => {
    const proposta = propostaUnita(
      riga.media, riga.giacenza, riga.pacchetti_per_unita, giorniCopertura, distanza, pct,
    );
    const proposti = proposta.unita;
    const unita = riga.corretto_a_mano ? Number(riga.unita) : proposti;
    const pacchetti = unita * Number(riga.pacchetti_per_unita || 0);
    const dataFine = proposta.giorniFine == null
      ? null
      : addDays(inizio, proposta.giorniFine);
    const proiezione = proiezioneDopoOrdine(
      riga.media,
      riga.giacenza,
      riga.pacchetti_per_unita,
      unita,
      distanza,
      giorniCopertura,
      dataConsegna,
    );
    return {
      ...riga,
      unita_proposte: proposti,
      unita,
      corretto_a_mano: unita !== proposti,
      pacchetti,
      kg: roundKg(unita * Number(riga.kg_per_unita || 0)),
      importo: roundMoney(pacchetti * Number(riga.prezzo || 0)),
      giorni_fine: proposta.giorniFine,
      data_fine: dataFine,
      urgenza: urgenzaDataFine(proposta.giorniFine, distanza, giorniCopertura),
      giorni_alla_consegna: distanza,
      giacenza_dopo_consegna: Number(proiezione.giacenzaDopoConsegna.toFixed(1)),
      residuo_copertura: Number(proiezione.residuoCopertura.toFixed(1)),
      giorni_con_ordine: proiezione.giorniConOrdine,
      data_copre_fino: proiezione.dataCopreFino,
      urgenza_copertura: proiezione.urgenzaCopertura,
    };
  });
}

export function totaliOrdine(righe) {
  const attivi = righe.filter(riga => Number(riga.unita) > 0);
  return {
    articoli: attivi.length,
    stecche: attivi.reduce((sum, riga) => sum + Number(riga.unita || 0), 0),
    kg: roundKg(attivi.reduce((sum, riga) => sum + Number(riga.kg || 0), 0)),
    importo: roundMoney(attivi.reduce((sum, riga) => sum + Number(riga.importo || 0), 0)),
  };
}

export function fraseCopertura(giorniAlla, giorniCopertura, scortaPct = DEFAULT_SCORTA_PCT) {
  const pct = normalizzaScortaPct(scortaPct);
  const vende = giorniAlla <= 0
    ? 'Fino alla consegna non restano giorni di vendita'
    : giorniAlla === 1
      ? 'Fino alla consegna si vende ancora 1 giorno'
      : `Fino alla consegna si vendono ancora ${giorniAlla} giorni`;
  return `${vende}; poi la merce deve bastare ${giorniCopertura} giorni al ${pct}% di scorta. Tabacchi in stecche/kg; dispositivi e solidi in confezioni (pezzi per conf. come in TabaUno).`;
}

export function formattaFinisce(iso) {
  if (!iso) return '—';
  const nomi = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab'];
  const day = parseIso(iso);
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  return `${nomi[day.getDay()]} ${dd}/${mm}`;
}

export function formattaResiduo(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value);
  const abs = Math.abs(n);
  const testo = Number.isInteger(abs) || Math.abs(abs - Math.round(abs)) < 0.05
    ? String(Math.round(abs))
    : abs.toLocaleString('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (n > 0.05) return `${testo} pz`;
  if (n < -0.05) return `−${testo} pz`;
  return '0 pz';
}

export function formattaChiusura(iso) {
  if (!iso) return '—';
  const day = parseIso(iso);
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  const yyyy = day.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export function quantitaElenco(riga) {
  if (sezioneDiRiga(riga) === 'tabacchi') {
    return `${Number(riga.kg || 0).toFixed(3)} kg`;
  }
  const pezzi = Number(riga.unita || 0) * Number(riga.pacchetti_per_unita || 0);
  return `${Number(riga.unita || 0)} conf. (${pezzi} pz)`;
}

export function elencoCopia(righe) {
  const attivi = [...righe].filter(riga => Number(riga.unita) > 0);
  const blocchi = SEZIONI_ORDINE.map(sezione => {
    const items = attivi
      .filter(riga => sezioneDiRiga(riga) === sezione.id)
      .sort((a, b) => String(a.descrizione).localeCompare(String(b.descrizione), 'it'));
    if (!items.length) return null;
    const righeTesto = items.map(riga => `${riga.aams}\t${riga.descrizione}\t${quantitaElenco(riga)}`);
    return [`## ${sezione.label}`, ...righeTesto].join('\n');
  }).filter(Boolean);
  return blocchi.join('\n\n');
}

export function conteggiSezioni(righe) {
  const out = {};
  for (const sezione of SEZIONI_ORDINE) {
    const items = righeSezione(righe, sezione.id);
    const attivi = items.filter(riga => Number(riga.unita) > 0);
    out[sezione.id] = {
      articoli: attivi.length,
      totali: items.length,
      stecche: attivi.reduce((sum, riga) => sum + Number(riga.unita || 0), 0),
      pezzi: attivi.reduce(
        (sum, riga) => sum + Number(riga.unita || 0) * Number(riga.pacchetti_per_unita || 0),
        0,
      ),
      kg: roundKg(attivi.reduce((sum, riga) => sum + Number(riga.kg || 0), 0)),
      importo: roundMoney(attivi.reduce((sum, riga) => sum + Number(riga.importo || 0), 0)),
    };
  }
  return out;
}

export function isoLocale(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function confrontaRighe(a, b, chiave = 'residuo', direzione = 'asc') {
  const dir = direzione === 'desc' ? -1 : 1;
  let cmp = 0;
  if (chiave === 'descrizione') {
    cmp = String(a.descrizione || '').localeCompare(String(b.descrizione || ''), 'it', { sensitivity: 'base' });
  } else if (chiave === 'importo') {
    cmp = Number(a.importo || 0) - Number(b.importo || 0);
  } else if (chiave === 'finisce') {
    const ga = a.giorni_fine == null ? 1e9 : Number(a.giorni_fine);
    const gb = b.giorni_fine == null ? 1e9 : Number(b.giorni_fine);
    cmp = ga - gb;
  } else {
    // residuo copertura: prima chi resta con meno (o in negativo)
    cmp = Number(a.residuo_copertura ?? 1e9) - Number(b.residuo_copertura ?? 1e9);
  }
  if (cmp === 0) {
    cmp = String(a.descrizione || '').localeCompare(String(b.descrizione || ''), 'it', { sensitivity: 'base' });
  }
  if (cmp === 0) {
    cmp = String(a.aams || '').localeCompare(String(b.aams || ''), 'it');
  }
  return cmp * dir;
}

export function gruppiDaOrdinare(righe, { chiave = 'residuo', direzione = 'asc', sezioneId = null } = {}) {
  const famiglieSezione = sezioneId
    ? (SEZIONI_ORDINE.find(sezione => sezione.id === sezioneId)?.famiglie || FAMIGLIE)
    : FAMIGLIE;
  const attivi = righe.filter(riga => Number(riga.unita) > 0);
  return famiglieSezione
    .map(famiglia => {
      const items = attivi
        .filter(riga => riga.famiglia === famiglia)
        .sort((a, b) => confrontaRighe(a, b, chiave, direzione));
      const subtotale = roundMoney(items.reduce((sum, riga) => sum + Number(riga.importo || 0), 0));
      return { famiglia, items, subtotale };
    })
    .filter(group => group.items.length > 0);
}

export function altriArticoli(righe, { chiave = 'residuo', direzione = 'asc' } = {}) {
  return [...righe]
    .filter(riga => Number(riga.unita) <= 0)
    .sort((a, b) => confrontaRighe(a, b, chiave, direzione));
}

export { GIORNI, FAMIGLIE, DEFAULT_SCORTA_PCT, SCORTA_PCT_MIN, SCORTA_PCT_MAX };

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function roundKg(value) {
  return Math.round((Number(value) + Number.EPSILON) * 1000) / 1000;
}

function parseIso(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}

function addDays(iso, days) {
  const day = parseIso(iso);
  day.setDate(day.getDate() + days);
  return isoLocale(day);
}

function diffDays(later, earlier) {
  const ms = parseIso(later) - parseIso(earlier);
  return Math.round(ms / 86400000);
}
