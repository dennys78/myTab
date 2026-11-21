import assert from 'node:assert/strict';
import { applicaPortaleSuItems } from './portaleOverlay.js';

{
  const { items, applied } = applicaPortaleSuItems(
    [
      { descrizione: 'LOTTOMATICA', entrate: 1, uscite: 2, saldo: -1 },
      { descrizione: 'GRATTA E VINCI', entrate: 465, uscite: 237, saldo: 228 },
      { descrizione: 'MOONEY', entrate: 10, uscite: 0, saldo: 10 },
    ],
    {
      lotto: { entrate: 409.5, uscite: 127.5 },
      premi_lotterie_vista: { totale: { qta: 10, importo: 86 } },
    },
  );
  assert.deepEqual(applied, ['LOTTOMATICA', 'GRATTA E VINCI']);
  assert.equal(items[0].entrate, 409.5);
  assert.equal(items[0].uscite, 127.5);
  assert.equal(items[0].saldo, 282);
  assert.equal(items[0].from_portale, true);
  assert.equal(items[1].entrate, 465);
  assert.equal(items[1].uscite, 86);
  assert.equal(items[1].saldo, 379);
  assert.equal(items[2].entrate, 10);
}

{
  const { items, applied } = applicaPortaleSuItems(
    [{ descrizione: 'LOTTOMATICA', entrate: 1, uscite: 0, saldo: 1 }],
    { errore: 'offline' },
  );
  assert.deepEqual(applied, []);
  assert.equal(items[0].entrate, 1);
}

console.log('portaleOverlay.test.js: ok');
