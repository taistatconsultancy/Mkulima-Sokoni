import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402

UUID = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'


class VerifyDashboardSessionTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _post(self, payload):
        return self.client.post(
            '/api/auth/verify-dashboard-session',
            data=json.dumps(payload),
            content_type='application/json',
        )

    @patch('routes.auth.User.get_user_roles')
    @patch('routes.auth.User.get_user_by_firebase_uid')
    @patch('routes.auth.verify_firebase_token')
    def test_agro_blocked_from_farmer(self, mock_verify, mock_get, mock_roles):
        mock_verify.return_value = {'uid': 'uid-1'}
        mock_get.return_value = {
            'id': UUID,
            'firebase_uid': 'uid-1',
            'email': 'a@b.com',
            'role': 'agro-dealer',
        }
        mock_roles.return_value = ['agro-dealer']
        r = self._post({'id_token': 'fake.jwt', 'dashboard': 'farmer'})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertFalse(data.get('allowed'))
        self.assertEqual(data.get('redirect'), 'agro-dealer.html')

    @patch('routes.auth.User.get_user_roles')
    @patch('routes.auth.User.get_user_by_firebase_uid')
    @patch('routes.auth.verify_firebase_token')
    def test_farmer_ok(self, mock_verify, mock_get, mock_roles):
        mock_verify.return_value = {'uid': 'uid-2'}
        mock_get.return_value = {
            'id': UUID,
            'firebase_uid': 'uid-2',
            'email': 'f@b.com',
            'role': 'farmer',
        }
        mock_roles.return_value = ['farmer']
        r = self._post({'id_token': 'fake.jwt', 'dashboard': 'farmer'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json().get('allowed'))

    @patch('routes.auth.verify_firebase_token')
    def test_bad_token_401(self, mock_verify):
        mock_verify.return_value = None
        r = self._post({'id_token': 'bad', 'dashboard': 'farmer'})
        self.assertEqual(r.status_code, 401)


if __name__ == '__main__':
    unittest.main()
