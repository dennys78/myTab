# Strategia acquisizione IA (Gemini XML unificato)

> Documento di recovery: se cambia il modello Gemini (o il provider), ripristinare questo approccio.
> Aggiornato: 2026-07-24 — commit di riferimento: pipeline `unified_xml`.

---

## Idea centrale

**Non** fare 6–7 chiamate vision (classifica + main + footer + report).

**Sì**:

1. **Una sola** chiamata Gemini con tutte le foto (5 o 6)
2. Gemini restituisce **XML** strutturato
3. **Python in locale** parsa l’XML e applica le regole di business (saldi, overlay Lotto/Sisal/Mooney/Gratta, Differenza)

Motivo: meno RPM → meno 503/429; regole fisse in codice → meno errori sui campi giochi.

---

## Dove sta il codice

| Pezzo | File |
|--------|------|
| Prompt XML + parser + ruoli foto | `reconciliation/ai_acquisition.py` → `UNIFIED_ACQUISITION_XML_PROMPT`, `parse_unified_acquisition_xml`, `build_unified_image_roles` |
| Chiamata Gemini unificata | `reconciliation/views.py` → `_extract_gemini_unified_bundle`, `_extract_ai_with_gemini(..., unified=True, expect_xml=True)` |
| Entry 5/6 file | `reconciliation/views.py` → `_extract_closure_five_files` (ramo `provider == 'gemini'`) |
| Merge overlay in maschera | `merge_report_overlays_into_items` + `_parse_ai_closure_payload` |
| Default modello | `docker-compose.yml` → `GEMINI_VISION_MODEL=gemini-2.5-flash` |

Groq resta percorso **legacy** (classificazione + più chiamate), non è il piano per 5/6 foto.

---

## Ordine upload obbligatorio (Gemini)

### 6 foto

1. Riepilogo cassa (pagina 1)
2. Eventuale 2ª pagina riepilogo *(se serve; altrimenti le ultime 4 sono sempre i report)*
3. **Contabile Lottomatica**
4. **Mooney** (MOVIMENTO CONTANTE)
5. **Premi Gratta e Vinci**
6. **Borderò Sisal** (MOVIMENTO CONTANTI)

In codice (`build_unified_image_roles` con `n >= 6`):

```text
main_closure × (n-4) + lottomatica, mooney, gratta, sisal
```

### 5 foto

```text
main_closure × (n-3) + lottomatica, gratta, sisal
```

(senza Mooney)

Le etichette `IMG_1 … IMG_N` con il ruolo atteso vengono aggiunte in coda al prompt in `_extract_gemini_unified_bundle`.

---

## Prompt (fonte di verità operativa)

Il testo sotto è la copia di `UNIFIED_ACQUISITION_XML_PROMPT`. Se lo aggiorni in codice, aggiorna anche qui.

```
Ricevi N foto di una tabaccheria italiana (riepilogo cassa + report giochi).
Ogni foto è etichettata nel messaggio (IMG_1, IMG_2, …) con il ruolo atteso.

Restituisci SOLO un documento XML valido, senza markdown e senza testo fuori dal XML.
Schema obbligatorio:

<chiusura>
  <date>YYYY-MM-DD</date>
  <summary>
    <contanti>0.00</contanti>
    <pag_pos>0.00</pag_pos>
    <cassa_auto>0.00</cassa_auto>
    <reso_cont>0.00</reso_cont>
    <reso_auto>0.00</reso_auto>
    <distrib>0.00</distrib>
    <totale>0.00</totale>
  </summary>
  <items>
    <item descrizione="NOME" entrate="0.00" uscite="0.00"/>
  </items>
  <reports>
    <lottomatica entrate="0.00" uscite="0.00"/>
    <mooney entrate="0.00" uscite="0.00"/>
    <gratta uscite="0.00"/>
    <sisal entrate="0.00" uscite="0.00"/>
  </reports>
</chiusura>

Regole di lettura (OBBLIGATORIE):
1) Riepilogo cassa (main_closure): tutte le righe reparto con Entrate/Uscite (anche NUOVA SEZIONE GESTORI).
   summary = riga Contanti, Pag.Pos, Cassa Auto, Reso Cont., Reso Auto, Distrib., TOTALE (ultima colonna = totale).
2) Lottomatica (Contabile Giornaliero): SOLO Entrate Gioco e Uscite Gioco. VIETATO Aggio e Saldo.
3) Sisal (BORDERÒ MOVIMENTO CONTANTI): SOLO Vendite e |Pagamenti| del riquadro TOTALE. VIETATO il netto.
4) Mooney (MOVIMENTO CONTANTE): Totale ricevuta in entrate; uscite 0 se non ci sono pagamenti espliciti.
5) Gratta (Premi pagati): solo Totale premi in uscite (attributo uscite). Le entrate Gratta restano dal riepilogo.
6) Numeri con punto decimale (397.00). Valori assoluti positivi per entrate/uscite.
7) Se un report non è presente tra le foto, lascia 0.00. Non inventare.
8) descrizioni reparto in MAIUSCOLO.
```

Più, in runtime, il blocco:

```
Ordine foto in questa richiesta:
- IMG_1: ruolo atteso = …
…
Le immagini seguono esattamente questo ordine (IMG_1 prima, poi IMG_2, …).
```

---

## Regole locali (dopo il parse XML)

Applicare **sempre** in Python, non fidarsi del modello sul segno/saldo:

| Reparto | Fonte XML | Entrate | Uscite | Note |
|---------|-----------|---------|--------|------|
| **LOTTOMATICA** | `<lottomatica>` | Entrate Gioco | Uscite Gioco | Sovrascrive riga cassa. No Aggio/Saldo |
| **SISAL** | `<sisal>` | Vendite TOTALE | abs(Pagamenti) | No netto Borderò |
| **MOONEY** | `<mooney>` | Totale ricevuta | di solito 0 | Full replace |
| **GRATTA E VINCI** | `<gratta>` | dal riepilogo (`items`) | Totale premi | Solo uscite dal report |

- `saldo = entrate − uscite` (può essere **negativo**, es. Sisal 281 − 331.05)
- Entrate/uscite sempre in valore assoluto (`normalize_report_overlay`)
- Modalità 5/6 file (`with_reports`):  
  `Differenza = TOTALE − Σ(saldi reparti)`  
  `totale_cassetto = 0`

Esempi numerici di riferimento (documenti reali usati in calibrazione):

- Lottomatica: **397 / 193**
- Sisal: **281 / 331.05** (saldo −50.05)

---

## Trasporto Gemini (parametri che funzionano)

| Parametro | Valore consigliato |
|-----------|-------------------|
| Modello primario | `gemini-2.5-flash` (stabile; meno “high demand”) |
| Fallback | `gemini-flash-latest`, poi `gemini-3.5-flash`, poi lite |
| Env | `GEMINI_VISION_MODEL=…` (override) |
| Immagini prep | max_side **1600**, quality **80** |
| Retry shrink | 1600→1280→1024 |
| Timeout HTTP | **120 s** (chiamata unificata) |
| maxOutputTokens | **8192** |
| temperature | **0** |
| response_mime_type | **non** forzare JSON (serve XML testo) |
| Backoff 429/503 | 2s → 4s → 8s → 16s, poi modello successivo |
| Failover a Groq | **no** sul percorso unificato |

Job asincrono (upload → bozza `queued/processing` → poll status): resta necessario per non far scadere Nginx mentre Gemini elabora.

---

## Cosa NON rifare (lezioni imparate)

1. Trattare Gemini come Groq free-tier (compressione 720–800px, fail-fast 1s, 6 chiamate)
2. Classificazione IA per-foto su 6 immagini (lenta + scambia Contabile/Borderò)
3. Failover automatico a Groq quando Groq free non regge più 6 foto
4. Usare Aggio/Saldo Lottomatica o netto Sisal come entrate/uscite
5. Forzare `response_mime_type: application/json` sulla risposta XML

---

## Come recuperare se cambia il modello

1. Imposta `GEMINI_VISION_MODEL=<nuovo-modello>` in `.env` / `docker-compose`
2. Verifica che il modello supporti vision multi-immagine + output testo lungo
3. Tieni **invariati** prompt XML e parser locale (qui sopra)
4. Se il nuovo modello è saturo (503): allunga il backoff o prova prima un Flash “stabile” nella lista `_gemini_vision_model_candidates`
5. Se il modello preferisce JSON: o adatti il prompt allo stesso schema in JSON, o mantieni XML e disattivi `response_mime_type` JSON (come ora)
6. Rebuild:  
   `cd /path/to/myTaba && git pull && docker-compose up -d --build`

---

## Checklist test rapido (6 foto)

- [ ] Impostazioni → motore **Gemini**
- [ ] Ordine foto come sopra
- [ ] Anteprima: Lottomatica / Sisal / Mooney / Gratta popolati dai report
- [ ] Saldi negativi ammessi dove uscite > entrate
- [ ] `Differenza = TOTALE − somma saldi`
- [ ] In payload: `slot_strategy: unified_xml` (o equivalente in `image_types`)

---

## Prompt legacy (report singoli)

Ancora presenti in `ai_acquisition.py` per Groq / percorsi non unificati:

- `LOTTO_PROMPT`, `SISAL_PROMPT`, `MOONEY_PROMPT`, `GRATTA_PROMPT`
- `MAIN_CLOSURE_AI_PROMPT` in `views.py` (modalità 2 file)

Per 5/6 file con Gemini **non** servono: tutto passa dal prompt XML unificato.
