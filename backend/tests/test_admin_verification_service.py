import unittest
from unittest.mock import patch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.admin_verification_service import apply_verification_change


class AdminVerificationServiceSmokeTests(unittest.TestCase):
    @patch('services.admin_verification_service.VerificationAudit.insert')
    @patch('services.admin_verification_service.User.get_user_by_id')
    @patch('services.admin_verification_service.User.get_user_roles')
    @patch('services.admin_verification_service.FarmerProfile.profile_exists')
    @patch('services.admin_verification_service.FarmerProfile.get_profile_by_user_id')
    @patch('services.admin_verification_service.FarmerProfile.update_profile')
    def test_approve_farmer_complete_without_national_id(
        self,
        mock_update_profile,
        mock_get_profile,
        mock_profile_exists,
        mock_get_roles,
        mock_get_user,
        mock_audit_insert,
    ):
        mock_get_user.return_value = {'id': 'user-1', 'role': 'farmer'}
        mock_get_roles.return_value = ['farmer']
        mock_profile_exists.return_value = True
        mock_get_profile.return_value = {
            'id': 'farmer-profile-1',
            'farm_name': 'Wanjiku Farm',
            'location': 'Kiambu',
            'county': 'Kiambu',
            'national_id': '',
            'certification_status': 'pending',
        }
        mock_audit_insert.return_value = {'id': 'audit-1'}

        result = apply_verification_change(
            'user-1', 'approve', '', {'uid': 'admin-1', 'email': 'admin@example.com'}
        )

        self.assertEqual(result['new_status'], 'verified')
        mock_update_profile.assert_called_once()
        mock_audit_insert.assert_called_once()

    @patch('services.admin_verification_service.User.get_user_by_id')
    @patch('services.admin_verification_service.User.get_user_roles')
    @patch('services.admin_verification_service.FarmerProfile.profile_exists')
    @patch('services.admin_verification_service.FarmerProfile.get_profile_by_user_id')
    @patch('services.admin_verification_service.FarmerProfile.update_profile')
    def test_approve_farmer_incomplete_profile_returns_error(
        self,
        mock_update_profile,
        mock_get_profile,
        mock_profile_exists,
        mock_get_roles,
        mock_get_user,
    ):
        mock_get_user.return_value = {'id': 'user-1', 'role': 'farmer'}
        mock_get_roles.return_value = ['farmer']
        mock_profile_exists.return_value = True
        mock_get_profile.return_value = {
            'id': 'farmer-profile-1',
            'farm_name': '',
            'location': 'Nairobi',
            'county': 'Nairobi',
            'national_id': '12345678',
            'certification_status': 'pending',
        }

        with self.assertRaises(ValueError) as ctx:
            apply_verification_change('user-1', 'approve', '', {'uid': 'admin-1', 'email': 'admin@example.com'})

        self.assertIn('Farmer profile is incomplete', str(ctx.exception))
        mock_update_profile.assert_not_called()

    @patch('services.admin_verification_service.User.get_user_by_id')
    @patch('services.admin_verification_service.User.get_user_roles')
    @patch('services.admin_verification_service.BuyerProfile.profile_exists')
    @patch('services.admin_verification_service.BuyerProfile.get_profile_by_user_id')
    @patch('services.admin_verification_service.BuyerProfile.update_profile')
    def test_approve_buyer_incomplete_profile_returns_error(
        self,
        mock_update_profile,
        mock_get_profile,
        mock_profile_exists,
        mock_get_roles,
        mock_get_user,
    ):
        mock_get_user.return_value = {'id': 'user-2', 'role': 'buyer'}
        mock_get_roles.return_value = ['buyer']
        mock_profile_exists.return_value = True
        mock_get_profile.return_value = {
            'company_name': 'Demo Buyer',
            'location': '',
            'county': 'Kiambu',
            'national_id': '99999999',
            'verification_status': 'pending',
        }

        with self.assertRaises(ValueError) as ctx:
            apply_verification_change('user-2', 'approve', '', {'uid': 'admin-1', 'email': 'admin@example.com'})

        self.assertIn('Buyer profile is incomplete', str(ctx.exception))
        mock_update_profile.assert_not_called()


if __name__ == '__main__':
    unittest.main()
