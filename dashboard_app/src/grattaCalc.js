const GIORNI = [3, 5, 7, 9];

export function giorniAllaConsegna(oggi, ultimoChiuso, dataConsegna) {
  const inizio = oggi > ultimoChiuso ? oggi : addDays(ultimoChiuso, 1);
  return Math.max(0, diffDays(dataConsegna, inizio));
}

export function propostaPacchi(media, giacenza, bigliettiPacco, giorniCopertura, giorniAllaConsegna) {
  const biglietti = Number(bigliettiPacco) || 0;
  const alla = Math.max(0, Number(giacenza) - Number(media) * Number(giorniAllaConsegna));
  const servono = Number(media) * Number(giorniCopertura);
  const mancano = servono - alla;
  const soglia = 0.25 * biglietti;
  let pacchi = 0;
  if (biglietti > 0 && mancano >= soglia - 1e-9) {
    pacchi = Math.ceil(Math.round((mancano / biglietti) * 1e8) / 1e8 - 1e-9);
  }
  const giorniCoperti = Number(media) === 0 ? null : alla / Number(media);
  let gruppo = 'coperti';
  if (pacchi > 0) gruppo = 'ordinare';
  else if (giorniCoperti != null && giorniCoperti < Number(giorniCopertura) + 3) gruppo = 'occhio';
  return { allaConsegna: alla, pacchi, giorniCoperti, gruppo };
}

export function ricalcolaRighe(righe, { giorniCopertura, oggi, ultimoChiuso, dataConsegna }) {
  const distanza = giorniAllaConsegna(oggi, ultimoChiuso, dataConsegna);
  return righe.map(riga => {
    const proposta = propostaPacchi(
      riga.media, riga.giacenza, riga.biglietti_pacco, giorniCopertura, distanza,
    );
    const proposti = riga.escluso ? 0 : proposta.pacchi;
    const pacchi = riga.corretto_a_mano ? riga.pacchi : proposti;
    const giorniCoperti = Number(riga.media) === 0 ? null : proposta.allaConsegna / Number(riga.media);
    let gruppo = 'coperti';
    if (pacchi > 0) gruppo = 'ordinare';
    else if (giorniCoperti != null && giorniCoperti < Number(giorniCopertura) + 3) gruppo = 'occhio';
    return {
      ...riga,
      pacchi_proposti: proposti,
      pacchi,
      corretto_a_mano: pacchi !== proposti,
      importo: roundMoney(pacchi * Number(riga.valore_pacco)),
      giorni_coperti: giorniCoperti == null ? null : Math.round(giorniCoperti * 100) / 100,
      gruppo,
      giorni_alla_consegna: distanza,
    };
  });
}

export function totaleOrdine(righe) {
  const attivi = righe.filter(riga => Number(riga.pacchi) > 0);
  const importo = roundMoney(attivi.reduce((sum, riga) => sum + Number(riga.importo || 0), 0));
  const pacchi = attivi.reduce((sum, riga) => sum + Number(riga.pacchi || 0), 0);
  return {
    giochi: attivi.length,
    pacchi,
    importo,
    aggio: roundMoney(importo * 0.08),
    sottoMinimo: importo < 900,
  };
}

export function fraseCopertura(dataConsegna, giorniAlla, giorniCopertura) {
  const quando = `Arriva ${giornoSettimana(dataConsegna)} ${formattaGiorno(dataConsegna)}`;
  const dopo = `la merce deve bastare ${giorniCopertura} giorni.`;
  if (giorniAlla <= 0) return `${quando}: ${dopo}`;
  const vende = giorniAlla === 1
    ? 'prima della consegna si vende ancora 1 giorno'
    : `prima della consegna si vendono ancora ${giorniAlla} giorni`;
  return `${quando}: ${vende}, poi ${dopo}`;
}

export function giornoSettimana(iso) {
  const nomi = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato'];
  return nomi[parseIso(iso).getDay()];
}

export function formattaGiorno(iso) {
  const day = parseIso(iso);
  const dd = String(day.getDate()).padStart(2, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  return `${dd}/${mm}`;
}

export function isoLocale(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function domaniIso(oggi = new Date()) {
  const day = new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate() + 1);
  return isoLocale(day);
}

export { GIORNI };

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
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
