"""Reading a day's Zoom Phone logs, without Zoom."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from business_agent.calllogs import (
    COMPLETE_SECONDS,
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
