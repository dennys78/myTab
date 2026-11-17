import test from 'node:test';
import assert from 'node:assert/strict';
import {
  giorniAllaConsegna,
  propostaUnita,
  prossimoGiornoConsegna,
  unitaOrdine,
} from './tabacchiCalc.js';

test('giorni alla consegna dal 17/11 al lunedì 23/11', () => {
  assert.equal(giorniAllaConsegna('2026-11-17', '2026-11-16', '2026-11-23'), 6);
});

test('prossimo lunedì Logista dopo oggi', () => {
  assert.equal(prossimoGiornoConsegna('2026-11-17', 0), '2026-11-23');
});

test('unità d\'ordine per sigarette da 20', () => {
  assert.deepEqual(unitaOrdine(5.8, 290, 200), { pacchettiPerUnita: 10, kgPerUnita: 0.2 });
});

test('unità d\'ordine con minimi diversi', () => {
  assert.equal(unitaOrdine(10, 200, 300).pacchettiPerUnita, 6);
  assert.equal(unitaOrdine(8, 160, 500).pacchettiPerUnita, 10);
});

const ESEMPI = [
  { media: 7.33, giacenza: 40, u: 10, atteso: 6 },
  { media: 6.70, giacenza: 45, u: 10, atteso: 5 },
  { media: 7.02, giacenza: 54, u: 10, atteso: 4 },
  { media: 9.40, giacenza: 96, u: 10, atteso: 3 },
];

for (const esempio of ESEMPI) {
  test(`proposta ${esempio.media} → ${esempio.atteso} stecche a 7 giorni`, () => {
    const proposta = propostaUnita(esempio.media, esempio.giacenza, esempio.u, 7, 6);
    assert.equal(proposta.unita, esempio.atteso);
  });
}
