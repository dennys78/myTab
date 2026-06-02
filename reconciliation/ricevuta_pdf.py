from decimal import Decimal
from io import BytesIO
import base64
import mimetypes
from pathlib import Path

from django.template.loader import render_to_string

try:
    from weasyprint import HTML
except ImportError:  # pragma: no cover
    HTML = None

MONTHS_IT = (
    'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
    'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre',
)

DEFAULT_LOGO_CANDIDATES = (
    Path(__file__).resolve().parent.parent / 'dashboard_app/public/pwa-192x192.png',
    Path(__file__).resolve().parent.parent / 'dashboard_app/public/apple-touch-icon.png',
    Path(__file__).resolve().parent.parent / 'dashboard_app/public/favicon.svg',
)


def format_euro(amount):
    value = Decimal(str(amount)).quantize(Decimal('0.01'))
    text = f'{value:,.2f}'
    return '€ ' + text.replace(',', 'X').replace('.', ',').replace('X', '.')


def format_date_it(value):
    if not value:
        return ''
    return f'{value.day} {MONTHS_IT[value.month - 1]} {value.year}'


def _logo_data_uri():
    for path in DEFAULT_LOGO_CANDIDATES:
        if not path.exists():
            continue
        mime, _ = mimetypes.guess_type(path.name)
        mime = mime or 'application/octet-stream'
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'data:{mime};base64,{encoded}'
    return ''


def build_ricevuta_context(ricevuta):
    righe = []
    totale = Decimal('0')
    for row in ricevuta.righe.all():
        qty = int(row.quantita or 1)
        line_total = row.importo_unitario * qty
        totale += line_total
        righe.append({
            'tipo_label': row.get_tipo_display(),
            'descrizione': row.descrizione,
            'quantita': qty,
            'importo_unitario': format_euro(row.importo_unitario),
            'importo_totale': format_euro(line_total),
        })

    company = ricevuta.company
    cliente = ricevuta.cliente
    return {
        'company': company,
        'cliente': cliente,
        'ricevuta': ricevuta,
        'logo_data_uri': _logo_data_uri(),
        'righe': righe,
        'totale': format_euro(totale),
        'data_formattata': format_date_it(ricevuta.date),
        'emissione_formattata': format_date_it(ricevuta.created_at.date()),
    }


def render_ricevuta_pdf(ricevuta):
    if HTML is None:
        raise RuntimeError('WeasyPrint non installato.')

    html = render_to_string('reconciliation/ricevuta_pdf.html', build_ricevuta_context(ricevuta))
    buffer = BytesIO()
    HTML(string=html).write_pdf(buffer)
    return buffer.getvalue()
