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


class SharedWithCuriaTest(unittest.TestCase):
    def test_young_maori_is_shared(self):
        self.assertTrue(pools.is_shared_with_curia('Young Maori 500'))

    def test_sample_size_does_not_matter(self):
        self.assertTrue(pools.is_shared_with_curia('Young Maori 333'))

    def test_an_unlisted_poll_is_not_shared(self):
        self.assertFalse(pools.is_shared_with_curia('ACT 1000'))
        self.assertFalse(pools.is_shared_with_curia('NZNP 333'))
        self.assertFalse(pools.is_shared_with_curia('Waitaki 400'))

    def test_nz_maori_and_gen_maori_are_shared(self):
        # Added 20 Oct 2026: "Maori Numbers Oct 26" proved ID-and-phone
        # identical to the exhausted "Under 30 Maori" pool that caused the
        # original incident - same resource under Curia's renamed poll.
        self.assertTrue(pools.is_shared_with_curia('NZ Maori 500'))
        self.assertTrue(pools.is_shared_with_curia('Gen Maori 500'))


class MaxSafeDrawTest(unittest.TestCase):
    def test_a_shared_poll_is_capped_at_half(self):
        self.assertEqual(pools.max_safe_draw(1907, 'Young Maori 500'), 953)

    def test_a_non_shared_poll_is_never_capped(self):
        self.assertEqual(pools.max_safe_draw(1907, 'ACT 1000'), 1907)
        self.assertEqual(pools.max_safe_draw(1907, 'Waitaki 400'), 1907)

    def test_the_cap_is_floored_not_rounded(self):
        self.assertEqual(pools.max_safe_draw(5, 'Young Maori 500'), 2)

    def test_an_empty_pool_caps_to_zero_not_negative(self):
        self.assertEqual(pools.max_safe_draw(0, 'Young Maori 500'), 0)

    def test_a_custom_fraction_overrides_the_default(self):
        self.assertEqual(pools.max_safe_draw(100, 'Young Maori 500', fraction=0.25), 25)
