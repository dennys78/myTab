# Agente TabaUno su Windows

L'agente non apre porte. Ogni 10 secondi chiede a myTaba se c'è una chiusura da leggere e, solo allora, apre i database.

## Cosa copiare sul PC del negozio

La cartella `tabauno_sync` (non serve il resto di myTaba). Esempio:

```text
C:\myTaba\tabauno_sync\
```

Nella stessa cartella copia `nssm.exe` (https://nssm.cc/download, la versione a 64 bit).

Serve Python 3, da python.org, con "Add python.exe to PATH". Non servono librerie aggiuntive.

## Prima di installare

1. In myTaba, da amministratore: Impostazioni → PC negozio TabaUno → Genera token agente. Il token si vede una sola volta.
2. Copia `config.example.json` in `config.json`.
3. Compila `config.json`:
   - `tabauno_db`, `storico_db` e `magx_db`: percorsi veri, con due barre nel JSON (`C:\\TabaUno\\DB\\TabaUno.db`, `Db_MagX.db` nella stessa cartella)
   - `ordine_logista_path`: dove scrivere `Ordine_Logista.xls` (di solito `C:\\TabaUno\\DB\\Ordine_Logista.xls`). Se omesso, usa la stessa cartella di `tabauno_db`
   - `mytab_url`: `https://www.my-tab.uk`
   - `agent_token`: il token appena generato
   - `gratta`: `B`

## Installare il servizio

Tasto destro su `installa_servizio.bat` → Esegui come amministratore.

Il servizio si chiama TabaUnoAgent, parte da solo all'accensione del PC e si riavvia se si chiude. Il file `.bat` di avvio resta solo per una prova a finestra aperta.

Log: `C:\myTaba\logs\tabauno_agent.log`. Non contiene il token.

Per toglierlo: `disinstalla_servizio.bat` come amministratore.

## Prova

1. Nel portale, Acquisisci chiusure: accanto al pulsante deve comparire "PC negozio online".
2. Scegli la data e premi Importa da TabaUno.
3. Se nel log compare `lettura ... totale=...` e l'anteprima si riempie, è a posto.

### Deposito Ordine_Logista.xls

Da Ordine Tabacchi, con PC online, premi **Deposita in TabaUno**: l'agente scarica i byte già convertiti dal server (LibreOffice) e li scrive così come sono in `ordine_logista_path` (tmp + rename). Nel log compare `deposito id=... path=...`. Se TabaUno/Excel tiene il file aperto, errore chiaro senza retry silenziosi. Aggiorna `service.py` e riavvia TabaUnoAgent dopo ogni release.

Una lettura senza il portale, per controllare solo i database:

```bat
cd /d C:\myTaba
python -m tabauno_sync --date 2026-11-16 --db C:\TabaUno\DB\TabaUno.db --storico C:\TabaUno\DB\TabaUnoStorico.db --gratta B
```
