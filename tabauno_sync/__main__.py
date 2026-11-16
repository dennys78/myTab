"""CLI e avvio del ciclo di estrazione."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extract import TabaUnoError, extract_closure
from .service import run_service


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Estrae la chiusura giornaliera da TabaUno.')
    parser.add_argument('--service', action='store_true', help='Lascia acceso il ciclo di estrazione.')
    parser.add_argument('--config', help='File JSON di configurazione del servizio.')
    parser.add_argument('--date', help='Giorno da estrarre, YYYY-MM-DD.')
    parser.add_argument('--db', help='Percorso di TabaUno.db.')
    parser.add_argument('--storico', help='Percorso di TabaUnoStorico.db.')
    parser.add_argument('--gratta', default='B', choices=['A', 'B', 'a', 'b'])
    parser.add_argument('--output', help='File JSON di destinazione. Senza, stampa su stdout.')
    args = parser.parse_args(argv)

    try:
        if args.service:
            if not args.config:
                parser.error('--service richiede --config')
            run_service(args.config)
            return 0
        if not args.date or not args.db:
            parser.error('Servono --date e --db, oppure --service --config')
        payload = extract_closure(
            args.db,
            args.date,
            storico_path=args.storico,
            gratta=args.gratta,
        )
    except TabaUnoError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
