import unittest
from business_agent import pools


class NormaliseTest(unittest.TestCase):
    def test_drops_the_sample_size(self):
        self.assertEqual(pools.normalise('ACT 1000'), 'act')
        self.assertEqual(pools.normalise('NZNP 333'), 'nznp')
        self.assertEqual(pools.normalise('NZNP 500'), 'nznp')

    def test_keeps_a_multiword_name(self):
        self.assertEqual(pools.normalise('Te Tai Tonga 500'), 'te tai tonga')
        self.assertEqual(pools.normalise('Hauraki-Waikato 500'), 'hauraki-waikato')

    def test_tolerates_whitespace_and_case(self):
        self.assertEqual(pools.normalise('  act  1000 '), 'act')

    def test_empty(self):
        self.assertEqual(pools.normalise(''), '')
        self.assertEqual(pools.normalise(None), '')


class PoolForTest(unittest.TestCase):
    def test_nznp_and_act_share_one_master(self):
        self.assertEqual(pools.pool_for('NZNP 500'), pools.NZ_MASTER)
        self.assertEqual(pools.pool_for('ACT 1000'), pools.NZ_MASTER)
        self.assertEqual(pools.pool_for('NZNP 333'), pools.pool_for('ACT 500'))

    def test_a_per_day_poll_has_no_standing_pool(self):
        for poll in ('Waitaki 400', 'Te Tai Tonga 500', 'Mt Albert 400',
                     'Hauraki-Waikato 500', 'Waiariki 500', 'Rangitikei 400',
                     'Nelson 400', 'Corp 1000', 'Wgtn 1000'):
            self.assertIsNone(pools.pool_for(poll), poll)
            self.assertFalse(pools.is_standing(poll), poll)

    def test_is_standing(self):
        self.assertTrue(pools.is_standing('ACT 1000'))
        self.assertTrue(pools.is_standing('NZNP 333'))
