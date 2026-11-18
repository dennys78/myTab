import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tabauno_sync.service import (
    _request,
    load_config,
    ordine_logista_path,
    write_ordine_logista,
)


class _Response:
    status = 204

    def read(self):
        return b''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AgentRequestTests(unittest.TestCase):
    def test_request_uses_named_user_agent(self):
        seen = {}

        def capture(request, timeout=30):
            seen['ua'] = request.get_header('User-agent')
            return _Response()

        with patch('tabauno_sync.service.urllib.request.urlopen', capture):
            status, payload = _request(
                {'mytab_url': 'https://www.my-tab.uk', 'agent_token': 'segreto'},
                'GET',
                '/api/tabauno/agent/next/',
            )
        self.assertEqual(status, 204)
        self.assertIsNone(payload)
        self.assertEqual(seen['ua'], 'myTaba-TabaUnoAgent/1.0')
        self.assertNotIn('segreto', seen['ua'])


class OrdineLogistaDepositTests(unittest.TestCase):
    def test_default_path_next_to_tabauno_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'TabaUno.db'
            path = ordine_logista_path({
                'tabauno_db': str(db),
                'ordine_logista_path': '',
            })
            self.assertEqual(path, (Path(tmp) / 'Ordine_Logista.xls').resolve())

    def test_configured_path(self):
        path = ordine_logista_path({
            'tabauno_db': r'C:\TabaUno\DB\TabaUno.db',
            'ordine_logista_path': r'D:\Ordini\Ordine_Logista.xls',
        })
        self.assertEqual(str(path), r'D:\Ordini\Ordine_Logista.xls')

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'Ordine_Logista.xls'
            result = write_ordine_logista(target, b'\xd0\xcf\x11\xe0demo')
            self.assertEqual(result['bytes'], 8)
            self.assertTrue(result['verificato'])
            self.assertTrue(result['ok'])
            self.assertIn('generato correttamente', result['messaggio'])
            self.assertEqual(target.read_bytes(), b'\xd0\xcf\x11\xe0demo')
            self.assertFalse((target.parent / f'{target.name}.tmp').exists())

    def test_load_config_sets_ordine_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'config.json'
            cfg.write_text(
                '{"tabauno_db":"C:\\\\TabaUno\\\\DB\\\\TabaUno.db",'
                '"mytab_url":"https://www.my-tab.uk","agent_token":"x"}',
                encoding='utf-8',
            )
            loaded = load_config(cfg)
            self.assertEqual(loaded.get('ordine_logista_path'), '')


if __name__ == '__main__':
    unittest.main()
