"""Ciclo da lasciare acceso sul PC Windows del punto vendita."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from .extract import TabaUnoError, extract_closure


def load_config(path) -> dict:
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not config.get('tabauno_db'):
        raise TabaUnoError('Config: manca tabauno_db.')
    config.setdefault('storico_db', '')
    config.setdefault('gratta', 'B')
    config.setdefault('output_dir', 'output')
    config.setdefault('poll_seconds', 300)
    config.setdefault('mytab_url', '')
    config.setdefault('mytab_token', '')
    config.setdefault('company_id', None)
    return config


def _canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def write_if_changed(destination: Path, payload) -> bool:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if destination.is_file() and destination.read_text(encoding='utf-8') == text:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding='utf-8')
    return True


def post_closure(config, payload) -> dict:
    base = str(config.get('mytab_url') or '').rstrip('/')
    token = str(config.get('mytab_token') or '').strip()
    if not base or not token:
        return {'skipped': True}
    body = dict(payload)
    if config.get('company_id'):
        body['company_id'] = config['company_id']
    request = urllib.request.Request(
        f'{base}/api/closures/import-tabauno/',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise TabaUnoError(f'Import myTaba {exc.code}: {detail}') from exc


def sync_day(config, day: str) -> dict:
    payload = extract_closure(
        config['tabauno_db'],
        day,
        storico_path=config.get('storico_db') or None,
        gratta=config.get('gratta') or 'B',
    )
    output_dir = Path(config['output_dir'])
    destination = output_dir / f'{day}.json'
    changed = write_if_changed(destination, payload)
    posted = None
    if changed and not payload['verifiche']['senza_righe']:
        posted = post_closure(config, payload)
    return {'data': day, 'path': str(destination), 'changed': changed, 'posted': posted}


def run_once(config) -> list:
    today = date.today()
    days = [today.isoformat(), (today - timedelta(days=1)).isoformat()]
    output_dir = Path(config['output_dir'])
    results = []
    for day in days:
        if day != today.isoformat() and (output_dir / f'{day}.json').is_file():
            continue
        results.append(sync_day(config, day))
    return results


def run_service(config_path) -> None:
    config = load_config(config_path)
    interval = max(30, int(config.get('poll_seconds') or 300))
    while True:
        try:
            for result in run_once(config):
                print(f"{result['data']} {'aggiornato' if result['changed'] else 'invariato'}")
        except TabaUnoError as exc:
            print(f'errore: {exc}')
        time.sleep(interval)
