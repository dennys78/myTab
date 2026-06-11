"""Comandi Telegram per versamento contanti in banca."""

from __future__ import annotations

import re

VERSAMENTO_EXAMPLE = 'Versati 2343,20'

VERSAMENTO_HINT = (
    'Per registrare un versamento in banca scrivi:\n'
    f'{VERSAMENTO_EXAMPLE}\n\n'
    'Forme accettate:\n'
    '• Versati / Versato / Versata importo\n'
    '• Versamento / Versamenti importo\n'
    '• Versamento in banca importo\n'
    '• Deposito banca importo\n\n'
    'Poi conferma la data (sì = oggi, oppure gg/mm).'
)

VERSAMENTO_NEEDS_AMOUNT = (
    'Versamento in banca: indica l\'importo.\n\n'
    f'Esempio: {VERSAMENTO_EXAMPLE}\n'
    'oppure: Versamento 2343,20'
)

# Parola chiave versamento (con varianti e "in banca" opzionale)
_VERSAMENTO_KW = (
    r'(?:'
    r'versat[oaie]?(?:\s+in\s+banca)?'
    r'|versament[oi]?(?:\s+(?:in\s+)?banca)?'
    r'|deposito\s+(?:in\s+)?banca'
    r')'
)

VERSAMENTO_KEYWORD_ONLY_RE = re.compile(
    rf'(?i)^{_VERSAMENTO_KW}\s*$',
)

VERSAMENTO_WITH_AMOUNT_RE = re.compile(
    rf'(?i)^{_VERSAMENTO_KW}\s*\(?\s*([\d][\d.,\s€]*)\s*\)?\s*$',
)

VERSAMENTO_LIKE_RE = re.compile(
    r'(?i)(?:\bversat[oaie]?\b|\bversament[oi]?\b|deposito\s+(?:in\s+)?banca)',
)


def _parse_amount_token(text: str) -> float:
    cleaned = (text or '').strip().replace('€', '').replace(' ', '')
    if not re.fullmatch(r'\d{1,9}([.,]\d{1,2})?', cleaned):
        raise ValueError('Importo non valido')
    if ',' in cleaned:
        return float(cleaned.replace('.', '').replace(',', '.'))
    return float(cleaned)


def looks_like_versamento_keyword(text: str) -> bool:
    return bool(VERSAMENTO_LIKE_RE.search((text or '').strip()))


def parse_versamento_message(text: str):
    """
    Interpreta messaggi di versamento in banca.

    Ritorna:
      - {'importo': float} se riconosciuto con importo
      - {'needs_amount': True} se è solo la parola chiave (es. «versamenti»)
      - {'ambiguous': True} se sembra un versamento ma non è chiaro
      - None se il messaggio non riguarda i versamenti
    """
    raw = (text or '').strip()
    if not raw or raw.startswith('/'):
        return None

    if VERSAMENTO_KEYWORD_ONLY_RE.match(raw):
        return {'needs_amount': True}

    match = VERSAMENTO_WITH_AMOUNT_RE.match(raw)
    if match:
        try:
            importo = _parse_amount_token(match.group(1))
        except ValueError as exc:
            return {'ambiguous': True, 'reason': str(exc)}
        if importo <= 0:
            return {'ambiguous': True, 'reason': 'L\'importo deve essere maggiore di zero.'}
        return {'importo': importo}

    if looks_like_versamento_keyword(raw):
        return {'ambiguous': True}

    return None
