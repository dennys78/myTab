import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formattaResiduo,
  giorniAllaConsegna,
  proiezioneDopoOrdine,
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
    const proposta = propostaUnita(esempio.media, esempio.giacenza, esempio.u, 7, 6, 100);
    assert.equal(proposta.unita, esempio.atteso);
  });
}

test('proiezione dopo ordine: residuo a fine copertura', () => {
  const out = proiezioneDopoOrdine(2.3, 8, 10, 3, 5, 7, '2026-11-23');
  assert.equal(out.giacenzaDopoConsegna, 30);
  assert.ok(Math.abs(out.residuoCopertura - 13.9) < 0.05);
  assert.equal(out.urgenzaCopertura, 'normale');
  assert.equal(out.dataCopreFino, '2026-12-06');
  assert.equal(formattaResiduo(13.9), '+13,9');
  const sotto = proiezioneDopoOrdine(2.3, 8, 10, 0, 5, 7, '2026-11-23');
  assert.ok(sotto.residuoCopertura < 0);
  assert.equal(sotto.urgenzaCopertura, 'rossa');
});
