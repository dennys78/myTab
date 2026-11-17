import test from 'node:test';
import assert from 'node:assert/strict';
import { propostaPacchi } from './grattaCalc.js';

const CONTROLLO = [
  ['NUMERI FORTUNATI NEW', 11.55, 50, 150, 54],
  ['MILIARDARIO NEW', 10.6, 60, 300, 119],
  ['50X NEW', 7.76, 30, 300, 27],
  ['FAI SCOPA BONUS', 10.65, 75, 150, 97],
  ['CRUCIJOLLY', 9.1, 50, 150, 40],
  ['NEW TUTTO PER TUTTO', 3.51, 60, 300, 26],
  ['NUMERISSIMI', 13.1, 60, 300, 112],
  ["BUONDI'", 4.6, 150, 150, 91],
  ['DOPPIA SFIDA CLASSIC', 4.23, 60, 300, 43],
  ['20X NEW', 3.29, 60, 300, 18],
  ['DOPPIA SFIDA SMALL', 3.95, 50, 150, 9],
  ['GIOCHI DI NATALE SUPER', 1.84, 30, 300, 58],
  ['IL TURISTA PER SEMPRE', 2.56, 60, 300, 44],
  ['MEGA MILIARDARIO NEW', 3.56, 30, 300, 38],
  ['GIOCHI DI NATALE EXTRA', 3.32, 15, 300, 36],
  ['COLOR PUZZLE 10€', 1.21, 30, 300, 2],
  ['DOPPIA SFIDA SUPER', 1.21, 30, 300, 14],
  ['COLOR PUZZLE 5€', 1.23, 60, 300, 39],
  ['MAXI MILIARDARIO NEW', 1.79, 15, 300, 60],
  ['SUPER NUMERISSIMI', 1.56, 30, 300, 39],
  ['DUAL PLAY', 0.51, 60, 300, 45],
  ['LOTTERIA ITALIA 2026', 0.84, 20, 100, 73],
  ['GIOCHI DI NATALE', 8.93, 60, 300, 114],
  ["VIVA L'ESTATE MINI", 1.23, 75, 150, 68],
  ['ULTRA NUMERISSIMI', 0.74, 15, 300, 33],
  ['MILIONI DI DIAMANTI', 0.49, 10, 300, 18],
  ['100X NEW', 0.33, 15, 300, 26],
  ['NEW EXTRA TUTTO PER TUTTO', 0.16, 15, 300, 40],
  ['CASINÒ RICCO', 0.65, 30, 300, 22],
  ["VIVA L'ESTATE SUPER", 0.4, 30, 300, 18],
];

function ordinati(giorni) {
  const trovati = {};
  let totale = 0;
  for (const [nome, media, biglietti, valore, giacenza] of CONTROLLO) {
    const proposta = propostaPacchi(media, giacenza, biglietti, giorni, 1);
    if (proposta.pacchi) {
      trovati[nome] = proposta.pacchi;
      totale += proposta.pacchi * valore;
    }
  }
  return { trovati, totale };
}

test('5 giorni', () => {
  const { trovati, totale } = ordinati(5);
  assert.deepEqual(trovati, {
    '50X NEW': 1,
    CRUCIJOLLY: 1,
    'DOPPIA SFIDA SMALL': 1,
    'NUMERI FORTUNATI NEW': 1,
  });
  assert.equal(totale, 750);
});

test('7 giorni', () => {
  const { trovati, totale } = ordinati(7);
  assert.deepEqual(trovati, {
    'COLOR PUZZLE 10€': 1,
    '50X NEW': 2,
    CRUCIJOLLY: 1,
    'DOPPIA SFIDA SMALL': 1,
    'NUMERI FORTUNATI NEW': 1,
  });
  assert.equal(totale, 1350);
});

test('9 giorni', () => {
  const { trovati, totale } = ordinati(9);
  assert.deepEqual(trovati, {
    'COLOR PUZZLE 10€': 1,
    '50X NEW': 2,
    NUMERISSIMI: 1,
    CRUCIJOLLY: 2,
    'DOPPIA SFIDA SMALL': 1,
    'NUMERI FORTUNATI NEW': 2,
  });
  assert.equal(totale, 1950);
});
