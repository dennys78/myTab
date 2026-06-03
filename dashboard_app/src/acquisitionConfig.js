/** Modalità acquisizione IA per azienda (persistita in AppSetting). */
export const ACQUISITION_MODE_TWO = 'two_files';
export const ACQUISITION_MODE_FIVE = 'five_files';

export function maxFilesForAcquisitionMode(mode) {
  return mode === ACQUISITION_MODE_FIVE ? 6 : 2;
}

/** Protocollo 5 file: minimo 5 foto; 6ª opzionale = report Mooney. */
export function isValidFiveModeFileCount(count) {
  return count === 5 || count === 6;
}

/** Retrocompatibilità per acquisizione OCR legacy. */
export const MAX_ACQUISITION_FILES = 6;
