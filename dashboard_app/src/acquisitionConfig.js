/** Modalità acquisizione IA per azienda (persistita in AppSetting). */
export const ACQUISITION_MODE_TWO = 'two_files';
export const ACQUISITION_MODE_FIVE = 'five_files';

export function maxFilesForAcquisitionMode(mode) {
  // two_files: fino a 7 (foglio + Mooney + LIS + Sisal + Gratta + Lotto)
  // five_files: fino a 6
  return mode === ACQUISITION_MODE_FIVE ? 6 : 7;
}

/** Protocollo 5 file: minimo 5 foto; 6ª opzionale = report Mooney. */
export function isValidFiveModeFileCount(count) {
  return count === 5 || count === 6;
}

/** Inserimenti a mano in chiusura, criterio D3 Solution. */
export const MANUAL_VOCI_D3 = ['LOTTOMATICA', 'MOONEY', 'SISAL', 'GRATTA E VINCI'];

export function isAziendaD3(companyName) {
  return /d3/i.test(String(companyName || ''));
}

/** Sull'altra azienda lo scassettato non arriva da TabaUno: parte da 0 e lo scrive l'utente. */
export function scassettatoManuale(companyName) {
  const name = String(companyName || '').trim();
  return name.length > 0 && !isAziendaD3(name);
}

/** L'altra azienda usa lo stesso elenco e aggiunge LIS, con entrate e uscite. */
export function manualVociFor(mode, companyName) {
  const name = String(companyName || '');
  if (isAziendaD3(name)) return [...MANUAL_VOCI_D3];
  if (mode === ACQUISITION_MODE_TWO || name) return [...MANUAL_VOCI_D3, 'LIS'];
  return [...MANUAL_VOCI_D3];
}

export function manualVociHint(mode, companyName) {
  const base = 'Lottomatica, Mooney, Sisal e Gratta e Vinci';
  return manualVociFor(mode, companyName).includes('LIS')
    ? 'Lottomatica, Mooney, Sisal, Gratta e Vinci e LIS'
    : base;
}

/** Protocollo 2–7 file: foglio; Mooney; LIS; Lotto; Premi Gratta; Sisal. */
export function isValidTwoModeFileCount(count) {
  return count >= 1 && count <= 7;
}

/** Retrocompatibilità per acquisizione OCR legacy. */
export const MAX_ACQUISITION_FILES = 7;
