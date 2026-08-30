import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.profile_completeness import farmer_profile_complete, buyer_profile_complete


class ProfileCompletenessTests(unittest.TestCase):
    def test_farmer_complete_without_national_id(self):
        row = {
            'farm_name': 'Wanjiku Farm',
            'location': 'Kiambu',
            'county': 'Kiambu',
            'national_id': '',
        }
        self.assertTrue(farmer_profile_complete(row))

    def test_farmer_incomplete_missing_farm_name(self):
        row = {
            'farm_name': '',
            'location': 'Kiambu',
            'county': 'Kiambu',
        }
        self.assertFalse(farmer_profile_complete(row))

    def test_buyer_complete_without_national_id(self):
        row = {
            'company_name': 'Nairobi Market Ltd',
            'location': 'Nairobi',
            'county': 'Nairobi',
        }
        self.assertTrue(buyer_profile_complete(row))

    def test_buyer_incomplete_missing_county(self):
        row = {
            'company_name': 'Nairobi Market Ltd',
            'location': 'Nairobi',
            'county': '',
        }
        self.assertFalse(buyer_profile_complete(row))


if __name__ == '__main__':
    unittest.main()
