import unittest

from business_agent import board


class ScoreTest(unittest.TestCase):
    def test_brendons_weights_are_not_drifting(self):
        self.assertEqual(board.COMPLETES_WEIGHT, 0.75)
        self.assertEqual(board.AWAY_WEIGHT, 0.25)

    def test_best_completes_and_least_away_scores_one(self):
        s = board.scores({'best': (10.0, 2.0), 'worst': (2.0, 40.0)})
        self.assertEqual(s['best'], 1.0)
        self.assertEqual(s['worst'], 0.0)

    def test_less_time_away_scores_higher(self):
        s = board.scores({'a': (5.0, 5.0), 'b': (5.0, 50.0)})
        self.assertGreater(s['a'], s['b'])

    def test_completes_outweigh_away_three_to_one(self):
        # The caller with more completes wins even when they are away far more.
        # This is the whole point of 75/25 and it is what put Nilyn back on shift.
        s = board.scores({'volume': (10.0, 50.0), 'tidy': (2.0, 1.0)})
        self.assertGreater(s['volume'], s['tidy'])

    def test_everyone_identical_scores_top(self):
        s = board.scores({'a': (5.0, 5.0), 'b': (5.0, 5.0)})
        self.assertEqual(set(s.values()), {1.0})

    def test_no_history_is_no_score(self):
        self.assertEqual(board.scores({}), {})


class SnakeDraftTest(unittest.TestCase):
    def test_the_order_reverses_every_round(self):
        got = board.snake_draft(list('123456'), {'A': 3, 'B': 3})
        self.assertEqual(got['A'], ['1', '4', '5'])
        self.assertEqual(got['B'], ['2', '3', '6'])

    def test_it_is_not_round_robin(self):
        # Straight alternation would give A picks 1,3,5 - half a rank ahead
        # every round. The reversal is what cancels that.
        got = board.snake_draft(list('123456'), {'A': 3, 'B': 3})
        self.assertNotEqual(got['A'], ['1', '3', '5'])

    def test_a_poll_that_fills_early_drops_out(self):
        got = board.snake_draft(list('12345678'), {'A': 2, 'B': 6})
        self.assertEqual(len(got['A']), 2)
        self.assertEqual(len(got['B']), 6)
        self.assertEqual(sorted(got['A'] + got['B']), list('12345678'))

    def test_one_poll_is_a_plain_ranked_fill(self):
        self.assertEqual(board.snake_draft(list('123'), {'A': 3})['A'], list('123'))

    def test_never_exceeds_a_cap(self):
        got = board.snake_draft(list('123456789'), {'A': 2, 'B': 2})
        self.assertEqual(sum(len(v) for v in got.values()), 4)

    def test_short_of_people_leaves_polls_part_filled(self):
        got = board.snake_draft(['1', '2'], {'A': 3, 'B': 3})
        self.assertEqual(sum(len(v) for v in got.values()), 2)


class PlanDayTest(unittest.TestCase):
    SCORE = {'a': 0.9, 'b': 0.8, 'c': 0.7, 'd': 0.6}

    def test_ranked_callers_go_first(self):
        day = board.plan_day(['a', 'b', 'new'], {'P': 3}, self.SCORE)
        self.assertEqual([n for n, _, _ in day.polls['P']], ['a', 'b', 'new'])

    def test_a_yes_with_no_history_is_still_placed(self):
        # The rule from 26 Sep: unrankable is a property of the window, and a
        # pure ranking can never hand anybody a first shift.
        day = board.plan_day(['new'], {'P': 1}, self.SCORE)
        self.assertEqual(day.firsts, ['new'])
        self.assertEqual(day.filled, 1)

    def test_newest_joiner_gets_the_first_shift_first(self):
        day = board.plan_day(['old', 'newer'], {'P': 1}, {},
                             joined={'old': 1, 'newer': 9})
        self.assertEqual(day.firsts, ['newer'])

    def test_nobody_is_placed_on_a_day_they_did_not_tick(self):
        day = board.plan_day(['a'], {'P': 4}, self.SCORE)
        placed = [n for v in day.polls.values() for n, _, _ in v]
        self.assertEqual(placed, ['a'])
        self.assertEqual(day.gap, 3)

    def test_first_shift_callers_are_flagged_in_the_poll_lists(self):
        day = board.plan_day(['a', 'new'], {'P': 2}, self.SCORE)
        flags = {n: isnew for n, _, isnew in day.polls['P']}
        self.assertFalse(flags['a'])
        self.assertTrue(flags['new'])

    def test_more_volunteers_than_slots_drops_the_lowest_ranked(self):
        day = board.plan_day(['a', 'b', 'c', 'd'], {'P': 2}, self.SCORE)
        self.assertEqual(sorted(n for n, _, _ in day.polls['P']), ['a', 'b'])
        self.assertEqual(day.gap, 0)

    def test_a_ranked_caller_beats_a_first_shift_caller_for_a_scarce_slot(self):
        day = board.plan_day(['d', 'new'], {'P': 1}, self.SCORE)
        self.assertEqual(day.firsts, [])
        self.assertEqual([n for n, _, _ in day.polls['P']], ['d'])

    def test_need_is_the_sum_of_the_caps(self):
        day = board.plan_day([], {'P': 7, 'Q': 3}, {})
        self.assertEqual(day.need, 10)
        self.assertEqual(day.gap, 10)

    def test_the_no_count_is_carried_through(self):
        self.assertEqual(board.plan_day(['a'], {'P': 1}, self.SCORE, no=5).no, 5)


class PollBalanceTest(unittest.TestCase):
    def test_the_draft_keeps_the_polls_close(self):
        score = {c: 1.0 - i * 0.05 for i, c in enumerate('abcdefghij')}
        day = board.plan_day(list('abcdefghij'), {'P': 5, 'Q': 5}, score)
        bal = board.poll_balance(day)
        self.assertLess(abs(bal['P'] - bal['Q']), 0.05)

    def test_filling_one_poll_then_the_next_is_what_it_catches(self):
        score = {c: 1.0 - i * 0.05 for i, c in enumerate('abcdefghij')}
        stacked = board.Day(need=10, yes=10, no=0, caps={'P': 5, 'Q': 5})
        stacked.polls = {
            'P': [(c, score[c], False) for c in 'abcde'],
            'Q': [(c, score[c], False) for c in 'fghij'],
        }
        bal = board.poll_balance(stacked)
        self.assertGreater(abs(bal['P'] - bal['Q']), 0.2)

    def test_first_shift_callers_are_left_out_of_the_mean(self):
        day = board.plan_day(['a', 'new'], {'P': 2}, {'a': 0.8})
        self.assertEqual(board.poll_balance(day)['P'], 0.8)

    def test_a_poll_of_only_first_shift_callers_reads_zero(self):
        day = board.plan_day(['new'], {'P': 1}, {})
        self.assertEqual(board.poll_balance(day)['P'], 0.0)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.days = {
            'Sun': board.plan_day(['a', 'b'], {'P': 3}, {'a': 0.9, 'b': 0.5}, no=2),
            'Mon': board.plan_day(['a', 'b'], {'P': 2}, {'a': 0.9, 'b': 0.5}, no=1),
        }
        self.out = board.build(self.days, as_at={'utc': 'x'}, changes=[], new_joiners=[])

    def test_the_week_totals_add_up(self):
        self.assertEqual(self.out['totals'], {'need': 5, 'filled': 4, 'gap': 1, 'firsts': 0})

    def test_revenue_is_shifts_times_the_rate(self):
        self.assertEqual(self.out['revenue']['week_full'], 5 * 58.50)
        self.assertEqual(self.out['revenue']['week_secured'], 4 * 58.50)
        self.assertEqual(self.out['revenue']['week_at_risk'], 58.50)

    def test_secured_plus_at_risk_is_the_full_week(self):
        r = self.out['revenue']
        self.assertAlmostEqual(r['week_secured'] + r['week_at_risk'], r['week_full'], places=2)

    def test_the_rate_is_three_hours_at_19_50(self):
        self.assertEqual(board.PER_SHIFT, 19.5 * 3)

    def test_it_is_json_serialisable(self):
        import json
        self.assertIn('"totals"', json.dumps(self.out))
