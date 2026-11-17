import test from 'node:test';
import assert from 'node:assert/strict';
import { ACQUISITION_MODE_FIVE, ACQUISITION_MODE_TWO, manualVociForMode, manualVociHint } from './acquisitionConfig.js';

test('D3 Solution tiene i quattro inserimenti manuali', () => {
  assert.deepEqual(manualVociForMode(ACQUISITION_MODE_FIVE), [
    'LOTTOMATICA', 'MOONEY', 'SISAL', 'GRATTA E VINCI',
  ]);
  assert.equal(manualVociHint(ACQUISITION_MODE_FIVE), 'Lottomatica, Mooney, Sisal e Gratta e Vinci');
});

test('l\'altra azienda aggiunge LIS', () => {
  assert.deepEqual(manualVociForMode(ACQUISITION_MODE_TWO), [
    'LOTTOMATICA', 'MOONEY', 'SISAL', 'GRATTA E VINCI', 'LIS',
  ]);
  assert.equal(manualVociHint(ACQUISITION_MODE_TWO), 'Lottomatica, Mooney, Sisal, Gratta e Vinci e LIS');
});
