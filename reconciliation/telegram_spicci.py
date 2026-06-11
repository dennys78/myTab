"""Comando Telegram: uscita cassa per spicci / monete / monetine."""

from __future__ import annotations

import re

SPICCI_EXAMPLE = 'Spicci 50'
TIPO_USCITA = 'USCITA'

SPICCI_HINT = (
    'Per registrare un\'uscita spicci/monete scrivi:\n'
    f'{SPICCI_EXAMPLE}\n\n'
    'Forme accettate:\n'
    '• Spicci importo\n'
    '• Monete importo\n'
    '• Monetine importo\n\n'
    'Registra un movimento di uscita in cassa con la data del messaggio.'
)

SPICCI_NEEDS_AMOUNT = (
    'Uscita spicci/monete: indica l\'importo.\n\n'
    f'Esempio: {SPICCI_EXAMPLE}\n'
    'oppure: Monete 25,50'
)

_SPICCI_KW = r'(?:spicci(?:oli)?|monete|monetine)'

SPICCI_KEYWORD_ONLY_RE = re.compile(
    rf'(?i)^{_SPICCI_KW}\s*$',
)

SPICCI_WITH_AMOUNT_RE = re.compile(
    rf'(?i)^({_SPICCI_KW})\s*\(?\s*([\d][\d.,\s€]*)\s*\)?\s*$',
)

SPICCI_LIKE_RE = re.compile(
    rf'(?i)\b(?:{_SPICCI_KW})\b',
)


def _parse_amount_token(text: str) -> float:
    cleaned = (text or '').strip().replace('€', '').replace(' ', '')
    if not re.fullmatch(r'\d{1,9}([.,]\d{1,2})?', cleaned):
        raise ValueError('Importo non valido')
    if ',' in cleaned:
        return float(cleaned.replace('.', '').replace(',', '.'))
    return float(cleaned)


def _note_from_keyword(keyword: str) -> str:
    key = (keyword or '').strip().lower()
    if key.startswith('monetine'):
        return 'Monetine'
    if key.startswith('monete'):
        return 'Monete'
    return 'Spicci'


def looks_like_spicci_keyword(text: str) -> bool:
    return bool(SPICCI_LIKE_RE.search((text or '').strip()))


def parse_spicci_message(text: str):
    """
    Interpreta messaggi tipo «Spicci 50» / «Monete 25,50».

    Ritorna:
      - {'importo': float, 'descrizione': str} se riconosciuto
      - {'needs_amount': True} se manca l'importo
      - {'ambiguous': True} se non è chiaro
      - None se non riguarda spicci/monete
    """
    raw = (text or '').strip()
    if not raw or raw.startswith('/'):
        return None

    kw_only = re.match(rf'(?i)^({_SPICCI_KW})\s*$', raw)
    if kw_only:
        return {
            'needs_amount': True,
            'descrizione': _note_from_keyword(kw_only.group(1)),
        }

    match = SPICCI_WITH_AMOUNT_RE.match(raw)
    if match:
        try:
            importo = _parse_amount_token(match.group(2))
        except ValueError as exc:
            return {'ambiguous': True, 'reason': str(exc)}
        if importo <= 0:
            return {'ambiguous': True, 'reason': 'L\'importo deve essere maggiore di zero.'}
        return {
            'importo': importo,
            'descrizione': _note_from_keyword(match.group(1)),
            'tipo': TIPO_USCITA,
        }

    if looks_like_spicci_keyword(raw):
        return {'ambiguous': True}

    return None
