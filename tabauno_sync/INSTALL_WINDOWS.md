# Agente TabaUno su Windows

L'agente non apre porte. Ogni pochi secondi chiede a myTaba se c'è una chiusura da leggere e, solo in quel caso, apre `TabaUno.db`.

## Prova manuale

1. Copia `config.example.json` in `config.json`.
2. Imposta i percorsi dei database, `mytab_url` e `agent_token` (il token si genera in myTaba, Impostazioni).
3. Dalla cartella del progetto:

```bat
tabauno_sync\avvia_tabauno_sync.bat
```

Una data singola, senza parlare con il portale:

```bat
python -m tabauno_sync --date 2026-11-16 --db C:\TabaUno\DB\TabaUno.db --storico C:\TabaUno\DB\TabaUnoStorico.db --gratta B
```

## Servizio con NSSM

Scarica NSSM e, da un prompt amministratore, nella cartella del progetto:

```bat
nssm install TabaUnoAgent C:\Path\To\python.exe -m tabauno_sync --agent --config C:\myTaba\tabauno_sync\config.json
nssm set TabaUnoAgent AppDirectory C:\myTaba
nssm set TabaUnoAgent AppStdout C:\myTaba\logs\nssm-stdout.log
nssm set TabaUnoAgent AppStderr C:\myTaba\logs\nssm-stderr.log
nssm set TabaUnoAgent AppRotateFiles 1
nssm set TabaUnoAgent Start SERVICE_AUTO_START
nssm set TabaUnoAgent AppExit Default Restart
nssm set TabaUnoAgent AppRestartDelay 5000
nssm start TabaUnoAgent
```

Sostituisci `C:\Path\To\python.exe` e `C:\myTaba` con i percorsi reali. Il log applicativo è `logs\tabauno_agent.log` (rotazione 1 MB, 5 file). Non contiene il token.

Per aggiornare il codice: `nssm restart TabaUnoAgent`.
