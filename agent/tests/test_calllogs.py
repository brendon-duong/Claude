"""Reading a day's Zoom Phone logs, without Zoom."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from business_agent.calllogs import (
    COMPLETE_SECONDS,
    EARLIEST_START,
    IDLE_SECONDS,
    SHIFT_HOURS,
    MANILA,
    Call,
    ShiftCalls,
    by_caller,
    calls_for_day,
    for_rostered,
    parse_call,
)

DAY = date(2026, 9, 13)


def row(caller="Lia Villapaz", when="2026-09-13T06:05:00Z", seconds=180,
        result="Connected", callee="+6421234567"):
    return {
        "caller_name": caller,
        "caller_number": "+63288001",
        "callee_number": callee,
        "date_time": when,
        "duration": seconds,
        "result": result,
        "direction": "outbound",
    }


def call(caller="Lia Villapaz", hour=6, minute=0, seconds=180, result="Connected"):
    return Call(
        caller=caller,
        caller_number="+63288001",
        callee_number="+6421234567",
        started=datetime(2026, 9, 13, hour, minute, tzinfo=timezone.utc),
        seconds=seconds,
        result=result,
    )


class TestParsingARow(unittest.TestCase):
    def test_reads_the_fields_an_audit_needs(self):
        parsed = parse_call(row())
        self.assertEqual(parsed.caller, "Lia Villapaz")
        self.assertEqual(parsed.seconds, 180)
        self.assertEqual(parsed.result, "Connected")
        self.assertTrue(parsed.answered)

    def test_an_unanswered_call_is_not_answered(self):
        self.assertFalse(parse_call(row(result="No Answer")).answered)

    def test_auto_recorded_is_what_a_picked_up_call_looks_like(self):
        # Zoom's name for it. 15,669 of the 33,875 calls in the first eleven
        # days of September, median 14s, longest 47 minutes.
        self.assertTrue(parse_call(row(result="Auto Recorded")).answered)

    def test_call_connected_is_a_dialler_state_not_a_conversation(self):
        # The guess that scored zero completes for everybody. 5,579 rows, none
        # of them longer than seven seconds.
        self.assertFalse(parse_call(row(result="Call connected", seconds=5)).answered)

    def test_a_cancelled_call_is_not_answered(self):
        self.assertFalse(parse_call(row(result="Call Cancel", seconds=0)).answered)
        self.assertFalse(parse_call(row(result="Voicemail")).answered)
        self.assertFalse(parse_call(row(result="Hang up")).answered)

    def test_zooms_other_field_names_are_accepted(self):
        # The Phone API has used both spellings across versions. Reading only
        # one of them would silently return zero calls after an upgrade.
        parsed = parse_call({
            "owner_name": "Leizel Chun",
            "callee_did_number": "+6421234567",
            "start_time": "2026-09-13T06:05:00Z",
            "duration_seconds": "240",
            "status": "Answered",
        })
        self.assertEqual(parsed.caller, "Leizel Chun")
        self.assertEqual(parsed.seconds, 240)
        self.assertTrue(parsed.answered)

    def test_a_row_with_no_timestamp_is_dropped_not_guessed(self):
        self.assertIsNone(parse_call({"caller_name": "Nobody"}))

    def test_a_row_with_an_unreadable_timestamp_is_dropped(self):
        self.assertIsNone(parse_call(row(when="not a date")))

    def test_a_missing_duration_reads_as_zero_rather_than_failing(self):
        payload = row()
        del payload["duration"]
        self.assertEqual(parse_call(payload).seconds, 0)

    def test_a_negative_duration_is_floored_at_zero(self):
        self.assertEqual(parse_call(row(seconds=-30)).seconds, 0)


class TestTheManilaDay(unittest.TestCase):
    """Curia quotes shifts in Manila time; Zoom answers in UTC."""

    def test_a_call_in_the_manila_evening_belongs_to_the_manila_date(self):
        # 2026-09-13 22:30 Manila is 14:30 UTC on the same date.
        parsed = parse_call(row(when="2026-09-13T14:30:00Z"))
        self.assertEqual(parsed.day, date(2026, 9, 13))

    def test_a_call_after_manila_midnight_is_the_next_day(self):
        # 16:30 UTC on the 13th is 00:30 Manila on the 14th. Filing this under
        # the 13th would credit a caller for the wrong shift.
        parsed = parse_call(row(when="2026-09-13T16:30:00Z"))
        self.assertEqual(parsed.day, date(2026, 9, 14))

    def test_a_two_pm_manila_shift_stays_on_its_own_date(self):
        # The real shift window: 2pm-5pm Manila is 06:00-09:00 UTC.
        for utc_hour in (6, 7, 8):
            parsed = parse_call(row(when=f"2026-09-13T0{utc_hour}:00:00Z"))
            self.assertEqual(parsed.day, date(2026, 9, 13))


class TestOneCallersShift(unittest.TestCase):
    def test_counts_attempts_and_answers_separately(self):
        shift = ShiftCalls("Lia", DAY, (
            call(result="Connected"),
            call(minute=5, result="No Answer"),
            call(minute=10, result="Connected"),
        ))
        self.assertEqual(shift.attempts, 3)
        self.assertEqual(shift.answered, 2)

    def test_talk_time_counts_only_answered_calls(self):
        # An unanswered call still has a duration — it rang. Counting it as
        # talk time would make a caller who reached nobody look productive.
        shift = ShiftCalls("Lia", DAY, (
            call(seconds=200, result="Connected"),
            call(minute=5, seconds=45, result="No Answer"),
        ))
        self.assertEqual(shift.talk_seconds, 200)

    def test_a_long_answered_call_counts_as_a_complete(self):
        shift = ShiftCalls("Lia", DAY, (call(seconds=200), call(minute=5, seconds=180)))
        self.assertEqual(shift.completes(), 2)

    def test_a_short_answered_call_is_not_a_complete(self):
        # Somebody picked up and got rid of them. That is a refusal, not a
        # survey, and counting it would let a caller inflate by dialling fast.
        shift = ShiftCalls("Lia", DAY, (call(seconds=20), call(minute=5, seconds=45)))
        self.assertEqual(shift.completes(), 0)
        self.assertEqual(shift.short_answers(), 2)

    def test_an_unanswered_call_is_never_a_complete_however_long(self):
        # A call that rang for four minutes reached nobody.
        shift = ShiftCalls("Lia", DAY, (call(seconds=240, result="No Answer"),))
        self.assertEqual(shift.completes(), 0)
        self.assertEqual(shift.short_answers(), 0)

    def test_a_call_exactly_on_the_threshold_counts(self):
        shift = ShiftCalls("Lia", DAY, (call(seconds=COMPLETE_SECONDS),))
        self.assertEqual(shift.completes(), 1)

    def test_one_second_under_the_threshold_does_not(self):
        shift = ShiftCalls("Lia", DAY, (call(seconds=COMPLETE_SECONDS - 1),))
        self.assertEqual(shift.completes(), 0)

    def test_the_threshold_can_be_changed_per_call(self):
        # It is a parameter because it has to be calibrated, not guessed once.
        shift = ShiftCalls("Lia", DAY, (call(seconds=100), call(minute=5, seconds=200)))
        self.assertEqual(shift.completes(threshold=90), 2)
        self.assertEqual(shift.completes(threshold=150), 1)
        self.assertEqual(shift.completes(threshold=300), 0)

    def test_completes_and_short_answers_together_are_every_answered_call(self):
        shift = ShiftCalls("Lia", DAY, (
            call(seconds=200), call(minute=5, seconds=20),
            call(minute=10, result="No Answer"),
        ))
        self.assertEqual(shift.completes() + shift.short_answers(), shift.answered)

    def test_time_inside_a_call_is_never_time_away(self):
        # Pernelia's real case: call 16 ran 6m27s, then call 17 started right
        # after. Measuring start-to-start would report six and a half minutes
        # off the phone for a shift she spent entirely on it.
        shift = ShiftCalls("Pernelia", DAY, (
            call(hour=6, minute=0, seconds=387),   # 6m27s
            call(hour=6, minute=7, seconds=120),
        ))
        self.assertEqual(shift.idle_time(), timedelta(0))
        self.assertEqual(shift.breaks(), [])

    def test_a_real_break_is_counted(self):
        # 06:00 for 1 min, nothing until 06:20 — nineteen minutes away.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=60),
            call(hour=6, minute=20, seconds=60),
        ))
        self.assertEqual(shift.idle_time(), timedelta(minutes=19))

    def test_every_break_is_added_up_not_just_the_longest(self):
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=60),
            call(hour=6, minute=10, seconds=60),   # 9 min gap
            call(hour=6, minute=25, seconds=60),   # 14 min gap
        ))
        self.assertEqual(shift.idle_time(), timedelta(minutes=23))
        self.assertEqual(shift.longest_gap(), timedelta(minutes=14))

    def test_dialling_time_between_calls_is_not_a_break(self):
        # Twenty seconds to hang up, read the next number and dial. Counting
        # these would punish a fast caller for making more calls.
        shift = ShiftCalls("Lia", DAY, tuple(
            call(hour=6, minute=m, seconds=40) for m in (0, 1, 2, 3, 4)
        ))
        self.assertEqual(shift.idle_time(), timedelta(0))

    def test_the_break_threshold_can_be_moved(self):
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=60),
            call(hour=6, minute=3, seconds=60),    # a 2 min gap
        ))
        self.assertEqual(shift.idle_time(minimum=60), timedelta(minutes=2))
        self.assertEqual(shift.idle_time(minimum=300), timedelta(0))

    def test_breaks_say_when_as_well_as_how_long(self):
        # Three twenty-minute breaks and forty two-minute ones total the same
        # and mean different things, so the individual gaps are returned.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=60),
            call(hour=6, minute=20, seconds=60),
        ))
        when, how_long = shift.breaks()[0]
        self.assertEqual(when.hour, 6)
        self.assertEqual(when.minute, 1)
        self.assertEqual(how_long, timedelta(minutes=19))

    def test_a_call_finishing_inside_a_longer_one_invents_no_gap(self):
        # Two lines at once. Comparing neighbouring pairs would see the short
        # call end long before the next starts and report a break that the
        # caller was on the phone for.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=1800),  # 30 min, runs to 06:30
            call(hour=6, minute=1, seconds=60),    # ends 06:02, inside it
            call(hour=6, minute=30, seconds=60),
        ))
        self.assertEqual(shift.idle_time(), timedelta(0))

    def test_a_shift_with_one_call_has_no_idle_time(self):
        self.assertEqual(ShiftCalls("Lia", DAY, (call(),)).idle_time(), timedelta(0))

    def test_the_default_break_threshold_is_one_minute(self):
        self.assertEqual(IDLE_SECONDS, 60)

    def test_the_longest_gap_is_measured_end_to_start(self):
        # 06:00 for 60s, then 06:30 -> a 29-minute gap, not 30.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=60),
            call(hour=6, minute=30, seconds=60),
        ))
        self.assertEqual(shift.longest_gap(), timedelta(minutes=29))

    def test_a_long_call_is_not_a_gap(self):
        # Twenty minutes on one call is work, not absence. Measuring gaps from
        # start to start would report it as twenty minutes off the phone.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=6, minute=0, seconds=1200),
            call(hour=6, minute=20, seconds=60),
        ))
        self.assertEqual(shift.longest_gap(), timedelta(0))

    def test_a_single_call_has_no_gap(self):
        self.assertEqual(ShiftCalls("Lia", DAY, (call(),)).longest_gap(), timedelta(0))

    def test_first_and_last_bound_the_shift(self):
        shift = ShiftCalls("Lia", DAY, (call(hour=8), call(hour=6), call(hour=7)))
        self.assertEqual(shift.first_call.hour, 6)
        self.assertEqual(shift.last_call.hour, 8)


class TestTheThreeHourShift(unittest.TestCase):
    """A shift is three hours of calling, not a fixed clock window."""

    def full_day(self):
        # 1:30pm Manila is 05:30 UTC. A caller genuinely on the phone: a call
        # every three minutes lasting 150s, so the 30s between them is dialling
        # and not a break. Ten-minute spacing would be eight-minute gaps, which
        # the floor would rightly count as time away from the phone.
        return ShiftCalls("Lia", DAY, tuple(
            call(hour=5 + (30 + m) // 60, minute=(30 + m) % 60, seconds=150)
            for m in range(0, 181, 3)
        ))

    def test_the_clock_starts_at_the_callers_own_first_call(self):
        shift = ShiftCalls("Lia", DAY, (call(hour=7, minute=0),))
        # 07:00 UTC is 3pm Manila — a late start, and that is the start.
        self.assertEqual(shift.started_at().hour, 15)

    def test_starting_before_the_earliest_time_does_not_start_the_clock(self):
        # One call at noon, then the real shift. Counting from noon would let
        # the three hours run out before the work began.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=4, minute=0, seconds=60),    # 12:00 Manila
            call(hour=7, minute=0, seconds=60),
        ))
        self.assertEqual(
            (shift.started_at().hour, shift.started_at().minute), EARLIEST_START
        )

    def test_the_shift_ends_when_the_last_call_ends_not_when_it_starts(self):
        # A six-minute call at the end is six minutes of work.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=5, minute=30, seconds=60),
            call(hour=8, minute=24, seconds=360),
        ))
        self.assertEqual((shift.finished_at().hour, shift.finished_at().minute), (16, 30))

    def test_a_full_three_hours_leaves_no_shortfall(self):
        self.assertEqual(self.full_day().shortfall(), timedelta(0))

    def test_dialling_between_calls_is_not_a_break(self):
        # Sixty-one short gaps. If they counted, the most productive caller on
        # the team would read as the idlest one.
        shift = self.full_day()
        self.assertEqual(shift.idle_time(), timedelta(0))
        self.assertEqual(shift.worked(), shift.span())
        self.assertGreaterEqual(shift.worked(), timedelta(hours=3))

    def test_a_short_shift_is_reported_by_how_much(self):
        # 1:30pm to 3:30pm Manila — two hours, so an hour short.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=5, minute=30, seconds=60),
            call(hour=7, minute=30, seconds=60),
        ))
        # Two hours of span, almost all of it one long break.
        self.assertEqual(shift.span(), timedelta(hours=2, minutes=1))
        self.assertGreater(shift.shortfall(), timedelta(hours=2))

    def test_breaks_come_out_of_the_three_hours(self):
        # Turning up for three hours and spending one of them away is not a
        # three-hour shift. Measuring the span alone would say it was.
        shift = ShiftCalls("Lia", DAY, tuple(
            call(hour=5 + (30 + m) // 60, minute=(30 + m) % 60, seconds=120)
            for m in list(range(0, 61, 10)) + list(range(121, 182, 10))
        ))
        self.assertGreaterEqual(shift.span(), timedelta(hours=3))
        self.assertGreater(shift.idle_time(), timedelta(minutes=55))
        self.assertGreater(shift.shortfall(), timedelta(minutes=55))

    def test_worked_time_is_the_span_minus_the_breaks(self):
        shift = ShiftCalls("Lia", DAY, (
            call(hour=5, minute=30, seconds=60),
            call(hour=6, minute=31, seconds=60),   # a 60 min break
        ))
        self.assertEqual(shift.span(), timedelta(hours=1, minutes=2))
        self.assertEqual(shift.idle_time(), timedelta(hours=1))
        self.assertEqual(shift.worked(), timedelta(minutes=2))

    def test_a_shift_cannot_be_covered_by_two_calls_hours_apart(self):
        # One call at 1:30, one at 4:30, nothing between. The span is three
        # hours; the work is not.
        shift = ShiftCalls("Lia", DAY, (
            call(hour=5, minute=30, seconds=60),
            call(hour=8, minute=29, seconds=60),
        ))
        self.assertGreaterEqual(shift.span(), timedelta(hours=2, minutes=59))
        self.assertGreater(shift.shortfall(), timedelta(hours=2, minutes=55))

    def test_a_day_with_no_calls_has_no_times(self):
        empty = ShiftCalls("Lia", DAY, ())
        self.assertIsNone(empty.started_at())
        self.assertIsNone(empty.finished_at())
        self.assertEqual(empty.span(), timedelta(0))
        self.assertEqual(empty.shortfall(), timedelta(hours=SHIFT_HOURS))


class TestGroupingADay(unittest.TestCase):
    def test_calls_are_grouped_by_who_made_them(self):
        grouped = by_caller([call("Lia"), call("Leizel", minute=5), call("Lia", minute=10)], DAY)
        self.assertEqual(sorted(grouped), ["leizel", "lia"])
        self.assertEqual(grouped["lia"].attempts, 2)

    def test_case_and_spacing_do_not_split_one_person_in_two(self):
        grouped = by_caller([call("Lia Villapaz"), call("  lia villapaz  ", minute=5)], DAY)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped["lia villapaz"].attempts, 2)

    def test_a_call_with_no_caller_name_is_left_out(self):
        self.assertEqual(by_caller([call("")], DAY), {})


class TestAgainstTheRoster(unittest.TestCase):
    def stub(self, rows):
        return lambda day, token: rows

    def test_returns_each_rostered_callers_own_calls(self):
        found, silent = for_rostered(
            DAY, ["Lia Villapaz", "Leizel Chun"],
            fetch=self.stub([row("Lia Villapaz"), row("Leizel Chun", seconds=90)]),
        )
        self.assertEqual(sorted(found), ["Leizel Chun", "Lia Villapaz"])
        self.assertEqual(silent, [])

    def test_a_rostered_caller_with_no_calls_is_named(self):
        # The whole point. Someone rostered who made no calls either did not
        # turn up or is logged under another name — both need a person to look.
        found, silent = for_rostered(
            DAY, ["Lia Villapaz", "Kharen Mae Pihana"],
            fetch=self.stub([row("Lia Villapaz")]),
        )
        self.assertEqual(list(found), ["Lia Villapaz"])
        self.assertEqual(silent, ["Kharen Mae Pihana"])

    def test_calls_from_people_not_rostered_are_ignored(self):
        found, _ = for_rostered(
            DAY, ["Lia Villapaz"],
            fetch=self.stub([row("Lia Villapaz"), row("Somebody Else")]),
        )
        self.assertEqual(list(found), ["Lia Villapaz"])

    def test_one_unparseable_row_does_not_lose_the_shift(self):
        found, _ = for_rostered(
            DAY, ["Lia Villapaz"],
            fetch=self.stub([row("Lia Villapaz"), {"caller_name": "Lia Villapaz"}]),
        )
        self.assertEqual(found["Lia Villapaz"].attempts, 1)

    def test_an_empty_day_names_everyone_as_silent(self):
        found, silent = for_rostered(DAY, ["Lia Villapaz"], fetch=self.stub([]))
        self.assertEqual(found, {})
        self.assertEqual(silent, ["Lia Villapaz"])


class TestCallsForDay(unittest.TestCase):
    def test_drops_rows_it_cannot_parse_rather_than_raising(self):
        # Zoom sending one malformed row must not cost the whole day's audit.
        rows = [row("Lia Villapaz"), {"junk": True}, row("Leizel Chun")]
        calls = calls_for_day(DAY, fetch=lambda day, token: rows)
        self.assertEqual([c.caller for c in calls], ["Lia Villapaz", "Leizel Chun"])

    def test_the_manila_timezone_is_eight_hours_ahead(self):
        self.assertEqual(MANILA.utcoffset(None), timedelta(hours=8))


if __name__ == "__main__":
    unittest.main()


class TestWhoACallBelongsTo(unittest.TestCase):
    """The agent is the Zoom owner. `caller_name` is only that on the way out."""

    def test_the_owner_is_the_agent_whichever_way_the_call_went(self):
        inbound = parse_call({**row("Anonymous"), "direction": "inbound",
                              "owner": {"name": "Lovely Salva", "extension_number": 1033}})
        self.assertEqual(inbound.agent, "Lovely Salva")

    def test_a_withheld_inbound_number_does_not_become_a_caller(self):
        # Five of these on 10 September 2026 were collected into a caller called
        # "Anonymous" with a three-hour shortfall. Nobody by that name exists.
        rows = [
            {**row("Anonymous"), "direction": "inbound", "owner": {"name": "Khars -"}},
            {**row("Anonymous", when="2026-09-13T06:20:00Z"), "direction": "inbound",
             "owner": {"name": "Josephus Chris Parages"}},
        ]
        grouped = by_caller([parse_call(r) for r in rows], DAY)
        self.assertNotIn("anonymous", grouped)
        self.assertEqual(sorted(grouped), ["josephus chris parages", "khars -"])

    def test_an_inbound_call_counts_toward_the_agents_total(self):
        # That is how Elaine counts total calls: every row that is the
        # agent's, both directions. Grouping this way matches her on 21 of 22.
        rows = [
            {**row("Lia Villapaz"), "owner": {"name": "Lia Villapaz"}},
            {**row("+6421000000", when="2026-09-13T06:20:00Z"), "direction": "inbound",
             "owner": {"name": "Lia Villapaz"}},
        ]
        grouped = by_caller([parse_call(r) for r in rows], DAY)
        self.assertEqual(grouped["lia villapaz"].attempts, 2)

    def test_without_an_owner_an_outbound_row_falls_back_to_the_caller(self):
        self.assertEqual(parse_call(row("Lia Villapaz")).agent, "Lia Villapaz")

    def test_without_an_owner_an_inbound_row_belongs_to_nobody(self):
        inbound = parse_call({**row("Anonymous"), "direction": "inbound"})
        self.assertEqual(inbound.agent, "")
        self.assertEqual(by_caller([inbound], DAY), {})

    def test_a_flat_owner_name_is_read_too(self):
        self.assertEqual(parse_call({**row(""), "owner_name": "Leizel Chun"}).owner, "Leizel Chun")


class TestNeverReachingTheShift(unittest.TestCase):
    """One test call at 10:37 is not a shift, and must not read like a no-show."""

    def only_before(self):
        # 02:37 UTC is 10:37 Manila — three hours before the earliest start.
        return ShiftCalls("Princess Matildo", DAY, (call(hour=2, minute=37, seconds=3),))

    def test_is_not_on_shift(self):
        self.assertFalse(self.only_before().on_shift)

    def test_has_no_window_so_it_cannot_run_backwards(self):
        # Before: started_at floored to 13:30 while finished_at stayed at
        # 10:37, and the report printed the window 13:30–10:37.
        shift = self.only_before()
        self.assertIsNone(shift.started_at())
        self.assertIsNone(shift.finished_at())
        self.assertEqual(shift.span(), timedelta(0))

    def test_the_calls_are_still_counted(self):
        self.assertEqual(self.only_before().attempts, 1)

    def test_a_caller_inside_the_window_is_on_shift(self):
        self.assertTrue(ShiftCalls("Lia", DAY, (call(hour=7),)).on_shift)

    def test_a_stray_early_call_plus_a_real_shift_is_still_on_shift(self):
        shift = ShiftCalls("Lia", DAY, (call(hour=4), call(hour=7)))
        self.assertTrue(shift.on_shift)
        self.assertEqual((shift.started_at().hour, shift.started_at().minute), EARLIEST_START)


class TestWhatCountsAsBeingThere(unittest.TestCase):
    """Counts use every call. Time uses only the calls that prove presence."""

    def working(self):
        # 1:30pm to 4:30pm Manila, a call every three minutes, no real gap.
        return [call(hour=5 + (30 + m) // 60, minute=(30 + m) % 60, seconds=150)
                for m in range(0, 181, 3)]

    def missed_inbound(self, hour, minute):
        return Call(caller="+6421000000", caller_number="+6421000000", callee_number="1033",
                    started=datetime(2026, 9, 13, hour, minute, tzinfo=timezone.utc),
                    seconds=0, result="No Answer", direction="inbound", owner="Lia")

    def test_a_missed_inbound_call_in_the_morning_is_not_a_break(self):
        # 23:53 UTC the day before is 7:53am Manila. Before this rule it opened
        # a 331-minute "break" and zeroed the whole shift.
        early = Call(caller="x", caller_number="x", callee_number="1033",
                     started=datetime(2026, 9, 12, 23, 53, tzinfo=timezone.utc),
                     seconds=0, result="No Answer", direction="inbound", owner="Lia")
        shift = ShiftCalls("Lia", DAY, tuple(self.working()) + (early,))
        self.assertEqual(shift.idle_time(), timedelta(0))
        self.assertEqual(shift.shortfall(), timedelta(0))

    def test_a_missed_inbound_call_after_the_shift_does_not_extend_it(self):
        # 10:18 UTC is 6:18pm Manila, well after the last outbound call.
        shift = ShiftCalls("Lia", DAY, tuple(self.working()) + (self.missed_inbound(10, 18),))
        self.assertEqual((shift.finished_at().hour, shift.finished_at().minute), (16, 32))
        self.assertEqual(shift.idle_time(), timedelta(0))

    def test_an_answered_inbound_call_is_presence(self):
        # Someone rang back and the caller picked up: they were there.
        picked_up = Call(caller="+6421000000", caller_number="+6421000000", callee_number="1033",
                         started=datetime(2026, 9, 13, 10, 18, tzinfo=timezone.utc),
                         seconds=200, result="Auto Recorded", direction="inbound", owner="Lia")
        shift = ShiftCalls("Lia", DAY, tuple(self.working()) + (picked_up,))
        self.assertTrue(picked_up.presence)
        self.assertEqual((shift.finished_at().hour, shift.finished_at().minute), (18, 21))
        self.assertEqual(shift.completes(), 62)   # and it counts as a survey

    def test_every_call_still_counts_toward_attempts(self):
        shift = ShiftCalls("Lia", DAY, tuple(self.working()) + (self.missed_inbound(10, 18),))
        self.assertEqual(shift.attempts, 62)
        self.assertEqual(shift.activity, 61)

    def test_only_missed_calls_is_no_activity_and_no_shift(self):
        shift = ShiftCalls("Lia", DAY, (self.missed_inbound(7, 0),))
        self.assertEqual(shift.activity, 0)
        self.assertFalse(shift.on_shift)

    def test_a_stray_noon_call_still_pins_the_clock_and_charges_the_wait(self):
        # Kept exactly as it was: the clock starts at 1:30, and the wait until
        # the first real call at 3pm is time away.
        shift = ShiftCalls("Lia", DAY, (call(hour=4, minute=0, seconds=60), call(hour=7, minute=0, seconds=60)))
        self.assertEqual((shift.started_at().hour, shift.started_at().minute), EARLIEST_START)
        self.assertEqual(shift.idle_time(), timedelta(hours=1, minutes=30))
