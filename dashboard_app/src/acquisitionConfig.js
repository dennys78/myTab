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

/** Protocollo 2–7 file: foglio; Mooney; LIS; Lotto; Premi Gratta; Sisal. */
export function isValidTwoModeFileCount(count) {
  return count >= 1 && count <= 7;
}

/** Retrocompatibilità per acquisizione OCR legacy. */
export const MAX_ACQUISITION_FILES = 7;
