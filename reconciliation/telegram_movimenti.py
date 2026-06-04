import re
from decimal import Decimal
from difflib import get_close_matches

from django.utils import timezone

from .models import MovimentoCassa
from .views import _get_saldo_cassa, _money

# Alias comuni per "Distributore" (errori di battitura).
DISTRIBUTORE_ALIASES = (
    'distributore',
    'distrubutore',
    'distrubutor',
    'distrubutori',
    'distrib',
    'distribut',
    'distributor',
    'distributori',
    'distrib.',
    'distr.',
)

MOVIMENTO_LINE_RE = re.compile(
    r'^\s*(?P<desc>.+?)\s+(?P<amount>[\d][\d.,\s]*)\s*€?\s*$',
    re.IGNORECASE,
)

UNCLEAR_HELP = (
    'Non ho capito il movimento da registrare.\n\n'
    'Formato: Descrizione importo\n'
    'Esempio: Distributore 505\n'
    'oppure: Distributore 505,50\n\n'
    'Registro un\'entrata in cassa con la data del messaggio Telegram.'
)


def _normalize_key(value):
    return re.sub(r'[^a-z0-9]+', '', (value or '').strip().lower())


def _parse_amount_token(text):
    cleaned = (text or '').strip().replace('€', '').replace(' ', '')
    if not re.fullmatch(r'\d{1,9}([.,]\d{1,2})?', cleaned):
        raise ValueError('Importo non valido')
    if ',' in cleaned:
        return float(cleaned.replace('.', '').replace(',', '.'))
    return float(cleaned)


def _canonical_description(raw_desc):
    desc = re.sub(r'\s+', ' ', (raw_desc or '').strip())
    if len(desc) < 2:
        return None

    key = _normalize_key(desc)
    if not key:
        return None

    if get_close_matches(key, [_normalize_key(a) for a in DISTRIBUTORE_ALIASES], n=1, cutoff=0.72):
        return 'Distributore'

    if len(desc) > 80:
        return None
    return desc[:1].upper() + desc[1:]


def parse_movimento_entrata_message(text):
    """
    Interpreta messaggi tipo "Distributore 505".
    Ritorna dict con descrizione/importo oppure None se non è un comando movimento.
    Solleva ValueError se il formato è riconosciuto ma ambiguo/non valido.
    """
    raw = (text or '').strip()
    if not raw:
        return None

    lowered = raw.lower()
    if lowered.startswith('/'):
        return None
    if re.match(r'(?i)^saldo(?:\s+cassa)?\s*$', raw):
        return None
    if re.match(r'(?i)^versat[oi]\b', raw):
        return None
    if re.match(r'(?i)^versament', raw):
        return None
    if re.match(r'(?i)^aggiungi\s+a\s+fondo\s', raw):
        return None
    if re.match(r'(?i)^preleva\s+da\s+fondo\s', raw):
        return None

    match = MOVIMENTO_LINE_RE.match(raw)
    if not match:
        # Prova a capire se l'utente voleva un movimento ma ha sbagliato formato.
        if re.search(r'\d', raw) and re.search(r'[a-zA-Zàèéìòù]', raw):
            raise ValueError(UNCLEAR_HELP)
        return None

    descrizione = _canonical_description(match.group('desc'))
    if not descrizione:
        raise ValueError(UNCLEAR_HELP)

    try:
        importo = _parse_amount_token(match.group('amount'))
    except ValueError as exc:
        raise ValueError(
            f'{UNCLEAR_HELP}\n\nDettaglio: {exc}.'
        ) from exc

    if importo <= 0:
        raise ValueError(
            f'{UNCLEAR_HELP}\n\nDettaglio: l\'importo deve essere maggiore di zero.'
        )

    return {
        'descrizione': descrizione,
        'importo': importo,
        'tipo': MovimentoCassa.TIPO_ENTRATA,
    }


def save_movimento_from_telegram(company, operator, parsed, movimento_date, *, source='Telegram'):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')

    importo_dec = Decimal(str(parsed['importo'])).quantize(Decimal('0.01'))
    if importo_dec <= 0:
        raise ValueError('Importo deve essere maggiore di zero')

    saldo_prec = _get_saldo_cassa(company)
    movimento = MovimentoCassa.objects.create(
        company=company,
        date=movimento_date,
        operator=(operator or 'Telegram')[:100],
        tipo=parsed.get('tipo', MovimentoCassa.TIPO_ENTRATA),
        importo=_money(importo_dec),
        saldo_precedente=saldo_prec,
        note=parsed['descrizione'],
        ricorda_promemoria=False,
    )
    saldo_attuale = float(_get_saldo_cassa(company))
    return movimento, float(saldo_prec), saldo_attuale


def message_local_date(update):
    msg = getattr(update, 'message', None)
    if not msg or not getattr(msg, 'date', None):
        return timezone.localdate()
    msg_dt = msg.date
    if timezone.is_aware(msg_dt):
        return timezone.localtime(msg_dt).date()
    return timezone.localdate(msg_dt)
