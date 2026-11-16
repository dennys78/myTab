import unittest
from unittest.mock import patch

from tabauno_sync.service import _request


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


if __name__ == '__main__':
    unittest.main()
