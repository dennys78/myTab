import test from 'node:test';
import assert from 'node:assert/strict';
import { ACQUISITION_MODE_FIVE, ACQUISITION_MODE_TWO, manualVociFor, manualVociHint } from './acquisitionConfig.js';

test('D3 Solution tiene i quattro inserimenti manuali', () => {
  assert.deepEqual(manualVociFor(ACQUISITION_MODE_FIVE, 'D3 Solution'), [
    'LOTTOMATICA', 'MOONEY', 'SISAL', 'GRATTA E VINCI',
  ]);
  assert.equal(manualVociHint(ACQUISITION_MODE_FIVE, 'D3 Solution'), 'Lottomatica, Mooney, Sisal e Gratta e Vinci');
});

test('l\'altra azienda aggiunge LIS con entrate e uscite', () => {
  assert.deepEqual(manualVociFor(ACQUISITION_MODE_FIVE, 'Tabaccheria'), [
    'LOTTOMATICA', 'MOONEY', 'SISAL', 'GRATTA E VINCI', 'LIS',
  ]);
  assert.deepEqual(manualVociFor(ACQUISITION_MODE_TWO, 'Tabaccheria').at(-1), 'LIS');
  assert.equal(manualVociHint(ACQUISITION_MODE_TWO, 'Tabaccheria'), 'Lottomatica, Mooney, Sisal, Gratta e Vinci e LIS');
});
