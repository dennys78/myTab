SIDEBAR_ITEMS = [
    {'id': 'dashboard', 'label': 'Dashboard', 'admin_only': True},
    {'id': 'chiusure', 'label': 'Chiusure Cassa', 'admin_only': True},
    {'id': 'acquisisci-ai', 'label': 'Acquisisci con IA', 'admin_only': False},
    {'id': 'versamenti', 'label': 'Versamenti', 'admin_only': False},
    {'id': 'movimenti', 'label': 'Movimenti', 'admin_only': False},
    {'id': 'fondo-cassa', 'label': 'Fondo Cassa', 'admin_only': False},
    {'id': 'impostazioni', 'label': 'Impostazioni', 'admin_only': False},
]

ALL_MENU_IDS = {item['id'] for item in SIDEBAR_ITEMS}
DEFAULT_ADMIN_MENU = [item['id'] for item in SIDEBAR_ITEMS]
DEFAULT_USER_MENU = [item['id'] for item in SIDEBAR_ITEMS if not item['admin_only']]


def default_sidebar_menu(is_admin):
    return list(DEFAULT_ADMIN_MENU if is_admin else DEFAULT_USER_MENU)


def normalize_sidebar_menu(menu_ids, is_admin):
    selected = [item_id for item_id in (menu_ids or []) if item_id in ALL_MENU_IDS]
    if not selected:
        return default_sidebar_menu(is_admin)
    return [item['id'] for item in SIDEBAR_ITEMS if item['id'] in selected]
