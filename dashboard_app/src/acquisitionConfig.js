/** Modalità acquisizione IA per azienda (persistita in AppSetting). */
export const ACQUISITION_MODE_TWO = 'two_files';
export const ACQUISITION_MODE_FIVE = 'five_files';

export function maxFilesForAcquisitionMode(mode) {
  return mode === ACQUISITION_MODE_FIVE ? 5 : 2;
}

/** Retrocompatibilità per acquisizione OCR legacy. */
export const MAX_ACQUISITION_FILES = 5;
