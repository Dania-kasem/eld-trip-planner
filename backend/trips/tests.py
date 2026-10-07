from datetime import datetime
from unittest.mock import patch

from django.test import SimpleTestCase

from . import hos
from .hos import DRIVING, OFF, ON_DUTY, SLEEPER

START = datetime(2026, 10, 5, 8, 0)


def run(m1, mph1, m2, mph2, cycle=0.0, start=START):
    return hos.plan_trip(m1, m1 / mph1 * 60, m2, m2 / mph2 * 60, cycle, start)


def check_rules(test, segs, cycle_used):
    """Walk the timeline and assert every HOS rule is respected."""
    driven = since_break = 0.0
    window_start = None
    cycle = cycle_used * 60
    for i, s in enumerate(segs):
        if i:
            test.assertEqual(segs[i - 1].end, s.start, "segments must be contiguous")
        m = s.minutes
        if s.status in (DRIVING, ON_DUTY) and window_start is None:
            window_start = s.start
        if s.status == DRIVING:
            driven += m
            since_break += m
            cycle += m
            test.assertLessEqual(driven, 11 * 60 + 1e-6, "11-hour driving limit")
            test.assertLessEqual(since_break, 8 * 60 + 1e-6, "30-min break after 8h driving")
            test.assertLessEqual(cycle, 70 * 60 + 1e-6, "70-hour limit")
            elapsed = (s.end - window_start).total_seconds() / 60
            test.assertLessEqual(elapsed, 14 * 60 + 1e-6, "14-hour window")
        else:
            if s.status == ON_DUTY:
                cycle += m
            if m >= 30:
                since_break = 0.0
            if s.status in (OFF, SLEEPER) and m >= 10 * 60:
                driven, window_start, since_break = 0.0, None, 0.0
            if s.status in (OFF, SLEEPER) and m >= 34 * 60:
                cycle = 0.0


def check_logs(test, logs):
    for log in logs:
        test.assertEqual(sum(log["totals_minutes"].values()), 1440)
        test.assertAlmostEqual(sum(log["totals_hours"].values()), 24.0, places=2)
        segs = log["segments"]
        test.assertEqual(segs[0]["start_minute"], 0)
        test.assertEqual(segs[-1]["end_minute"], 1440)
        for a, b in zip(segs, segs[1:]):
            test.assertEqual(a["end_minute"], b["start_minute"])


class ShortTripTests(SimpleTestCase):
    def test_short_trip_has_no_rests(self):
        segs = run(50, 50, 100, 50)
        kinds = [s.kind for s in segs]
        self.assertEqual(kinds, ["drive", "pickup", "drive", "dropoff"])
        check_rules(self, segs, 0)
        logs = hos.build_daily_logs(segs, START)
        self.assertEqual(len(logs), 1)
        check_logs(self, logs)
        self.assertEqual(logs[0]["totals_hours"][DRIVING], 3.0)
        self.assertEqual(logs[0]["total_miles_driving"], 150.0)

    def test_pickup_and_dropoff_are_one_hour(self):
        segs = run(10, 50, 10, 50)
        for s in segs:
            if s.kind in ("pickup", "dropoff"):
                self.assertEqual(s.minutes, 60)
                self.assertEqual(s.status, ON_DUTY)


class LongTripTests(SimpleTestCase):
    def test_multi_day_trip_obeys_all_rules(self):
        segs = run(300, 55, 2200, 55)
        check_rules(self, segs, 0)
        kinds = [s.kind for s in segs]
        self.assertIn("rest", kinds)
        self.assertIn("break", kinds)
        logs = hos.build_daily_logs(segs, START)
        self.assertGreaterEqual(len(logs), 3)
        check_logs(self, logs)

    def test_total_driven_miles_match(self):
        segs = run(300, 55, 2200, 55)
        self.assertAlmostEqual(sum(s.miles for s in segs), 2500, places=3)
        logs = hos.build_daily_logs(segs, START)
        self.assertAlmostEqual(sum(l["total_miles_driving"] for l in logs), 2500, delta=1.0)

    def test_fuel_at_least_every_1000_miles(self):
        segs = run(200, 55, 2700, 55)
        fuel_miles = [s.mile for s in segs if s.kind == "fuel"]
        self.assertGreaterEqual(len(fuel_miles), 2)
        marks = [0.0] + fuel_miles + [2900.0]
        for a, b in zip(marks, marks[1:]):
            self.assertLessEqual(b - a, 1000 + 1e-3)

    def test_break_after_8_hours(self):
        segs = run(10, 55, 600, 55)  # ~11 h driving, no stops that long
        brk = [s for s in segs if s.kind == "break"]
        self.assertTrue(brk)
        self.assertEqual(brk[0].minutes, 30)


class CycleTests(SimpleTestCase):
    def test_restart_inserted_when_cycle_exhausted(self):
        segs = run(100, 55, 500, 55, cycle=65)
        kinds = [s.kind for s in segs]
        self.assertIn("restart", kinds)
        restart = next(s for s in segs if s.kind == "restart")
        self.assertEqual(restart.minutes, 34 * 60)
        check_rules(self, segs, 65)
        check_logs(self, hos.build_daily_logs(segs, START))

    def test_no_restart_when_enough_hours(self):
        segs = run(100, 55, 200, 55, cycle=10)
        self.assertNotIn("restart", [s.kind for s in segs])

    def test_cycle_at_70_restarts_before_first_drive(self):
        segs = run(100, 55, 100, 55, cycle=70)
        self.assertEqual(segs[0].kind, "restart")
        check_rules(self, segs, 70)


class LogShapeTests(SimpleTestCase):
    def test_trip_ending_after_midnight_spans_two_days(self):
        late = datetime(2026, 10, 5, 20, 0)
        segs = run(300, 55, 300, 55, start=late)
        logs = hos.build_daily_logs(segs, late)
        self.assertGreaterEqual(len(logs), 2)
        check_logs(self, logs)
        self.assertEqual(logs[0]["segments"][0]["status"], OFF)  # pad before start

    def test_remarks_present_on_status_change(self):
        segs = run(50, 50, 100, 50)
        for s in segs:
            s.location = "Somewhere, VA"
        log = hos.build_daily_logs(segs, START)[0]
        self.assertGreaterEqual(len(log["remarks"]), 4)


class ApiTests(SimpleTestCase):
    def _fake_route(self, points):
        geom = [[37.54, -77.43], [38.9, -77.03], [40.71, -74.0]]
        return {
            "legs": [{"miles": 100.0, "seconds": 6000.0}, {"miles": 200.0, "seconds": 12000.0}],
            "miles": 300.0, "geometry": geom,
            "instructions": [{"leg": 0, "text": "Depart on I-95", "miles": 100.0}],
        }

    def test_plan_trip_endpoint(self):
        body = {
            "current_location": {"lat": 37.54, "lng": -77.43, "label": "Richmond, VA"},
            "pickup_location": {"lat": 38.9, "lng": -77.03, "label": "Washington, DC"},
            "dropoff_location": {"lat": 40.71, "lng": -74.0, "label": "New York, NY"},
            "current_cycle_used": 12,
            "start_time": "2026-10-05T06:00",
        }
        with patch("trips.views.osrm_route", self._fake_route), \
                patch.dict("os.environ", {"REVERSE_GEOCODE": "false"}):
            resp = self.client.post("/api/plan-trip/", body, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["summary"]["total_miles"], 300.0)
        self.assertEqual(data["stops"][0]["type"], "pickup")
        self.assertEqual(data["stops"][0]["location"], "Washington, DC")
        self.assertEqual(data["stops"][-1]["location"], "New York, NY")
        check_logs(self, data["logs"])

    def test_validation_errors(self):
        r = self.client.post("/api/plan-trip/", {"current_location": "x"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        full = {
            "current_location": {"lat": 1, "lng": 1}, "pickup_location": {"lat": 1, "lng": 1},
            "dropoff_location": {"lat": 1, "lng": 1}, "current_cycle_used": 99,
        }
        r = self.client.post("/api/plan-trip/", full, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("between 0 and 70", r.json()["error"])
