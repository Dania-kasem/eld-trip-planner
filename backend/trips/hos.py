"""
Hours-of-Service (HOS) simulation for a property-carrying driver on the
70-hour / 8-day schedule (49 CFR 395, FMCSA "Interstate Truck Driver's Guide").

This module is pure Python: no Django, no network. It takes leg distances and
durations and returns an ordered list of duty-status segments, then slices them
into 24-hour log sheets.

Rules implemented
-----------------
* 11-hour driving limit after 10 consecutive hours off duty
* 14-hour driving window (starts at the first on-duty/driving minute)
* 30-minute break after 8 cumulative hours of driving (any >= 30 min
  non-driving period counts)
* 70 hours on duty in 8 days; at the limit a 34-hour restart is inserted
* Fuel at least once every 1,000 miles (30 min, on duty not driving)
* 1 hour on duty for pickup and 1 hour for drop-off

Assumptions
-----------
* The driver starts fully rested (a valid 10 h off-duty just ended).
* "Current cycle used" hours are all inside the rolling 8-day window for the
  whole trip (nothing drops off). This is the conservative choice.
* The 10-hour rest is logged as Sleeper Berth; the 30-min break as Off Duty;
  the 34-hour restart as Off Duty.
* No adverse driving conditions, no split-sleeper pairing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

OFF, SLEEPER, DRIVING, ON_DUTY = "off_duty", "sleeper", "driving", "on_duty"

MAX_DRIVE_MIN = 11 * 60
WINDOW_MIN = 14 * 60
BREAK_AFTER_MIN = 8 * 60
BREAK_MIN = 30
REST_MIN = 10 * 60
RESTART_MIN = 34 * 60
CYCLE_LIMIT_MIN = 70 * 60
FUEL_INTERVAL_MILES = 1000.0
FUEL_STOP_MIN = 30
PICKUP_MIN = 60
DROPOFF_MIN = 60
EPS = 1e-6

KIND_NOTES = {
    "drive": "Driving",
    "pickup": "Pickup (loading)",
    "dropoff": "Drop-off (unloading)",
    "fuel": "Fuel stop",
    "break": "30-min rest break",
    "rest": "10-hr rest (sleeper berth)",
    "restart": "34-hr restart",
    "pad": "Off duty",
}


@dataclass
class Segment:
    status: str
    start: datetime
    end: datetime
    kind: str
    miles: float = 0.0      # miles driven inside this segment
    mile: float = 0.0       # trip mile marker at the segment start
    note: str = ""
    location: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0


class _Sim:
    def __init__(self, start: datetime, cycle_used_hours: float):
        self.t = start
        self.segments: list[Segment] = []
        self.mile = 0.0
        self.cycle = cycle_used_hours * 60.0   # minutes on duty in the 8-day window
        self.driven = 0.0                      # driving since last 10 h off
        self.window_start: Optional[datetime] = None
        self.since_break = 0.0                 # driving since last >=30 min non-driving
        self.since_fuel = 0.0                  # miles since last fuel

    def window_left(self) -> float:
        if self.window_start is None:
            return float(WINDOW_MIN)
        return WINDOW_MIN - (self.t - self.window_start).total_seconds() / 60.0

    def add(self, status: str, minutes: float, kind: str, miles: float = 0.0) -> None:
        seg = Segment(
            status=status,
            start=self.t,
            end=self.t + timedelta(minutes=minutes),
            kind=kind,
            miles=miles,
            mile=self.mile,
            note=KIND_NOTES[kind],
        )
        self.segments.append(seg)

        if status in (DRIVING, ON_DUTY):
            if self.window_start is None:
                self.window_start = self.t
            self.cycle += minutes
        if status == DRIVING:
            self.driven += minutes
            self.since_break += minutes
            self.since_fuel += miles
            self.mile += miles
        elif minutes >= BREAK_MIN - EPS:
            self.since_break = 0.0
        if status in (OFF, SLEEPER):
            if minutes >= REST_MIN - EPS:
                self.driven = 0.0
                self.window_start = None
                self.since_break = 0.0
            if minutes >= RESTART_MIN - EPS:
                self.cycle = 0.0
        self.t = seg.end

    def drive(self, miles: float, minutes: float) -> None:
        if miles <= EPS or minutes <= EPS:
            return
        per_min = miles / minutes
        remaining = miles
        while remaining > EPS:
            if self.cycle >= CYCLE_LIMIT_MIN - EPS:
                self.add(OFF, RESTART_MIN, "restart")
            elif self.driven >= MAX_DRIVE_MIN - EPS or self.window_left() <= EPS:
                self.add(SLEEPER, REST_MIN, "rest")
            elif self.since_break >= BREAK_AFTER_MIN - EPS:
                self.add(OFF, BREAK_MIN, "break")
            elif self.since_fuel >= FUEL_INTERVAL_MILES - EPS:
                self.add(ON_DUTY, FUEL_STOP_MIN, "fuel")
                self.since_fuel = 0.0
            else:
                chunk = min(
                    MAX_DRIVE_MIN - self.driven,
                    self.window_left(),
                    BREAK_AFTER_MIN - self.since_break,
                    CYCLE_LIMIT_MIN - self.cycle,
                    remaining / per_min,
                    (FUEL_INTERVAL_MILES - self.since_fuel) / per_min,
                )
                chunk_miles = min(chunk * per_min, remaining)
                self.add(DRIVING, chunk, "drive", miles=chunk_miles)
                remaining -= chunk_miles


def plan_trip(
    to_pickup_miles: float,
    to_pickup_minutes: float,
    to_dropoff_miles: float,
    to_dropoff_minutes: float,
    cycle_used_hours: float,
    start: datetime,
) -> list[Segment]:
    """Simulate the whole trip and return chronological duty segments."""
    sim = _Sim(start, cycle_used_hours)
    sim.drive(to_pickup_miles, to_pickup_minutes)
    sim.add(ON_DUTY, PICKUP_MIN, "pickup")
    sim.drive(to_dropoff_miles, to_dropoff_minutes)
    sim.add(ON_DUTY, DROPOFF_MIN, "dropoff")
    return sim.segments


def _pad(start: datetime, end: datetime, ref: Segment) -> Segment:
    return Segment(
        OFF, start, end, "pad", mile=ref.mile, note=KIND_NOTES["pad"],
        location=ref.location, lat=ref.lat, lng=ref.lng,
    )


def build_daily_logs(segments: list[Segment], start: datetime) -> list[dict]:
    """
    Slice segments into calendar-day log sheets (midnight to midnight, home
    terminal time). Each day's four statuses add up to exactly 24 hours.
    Minutes are integers measured from midnight (0..1440).
    """
    day0 = start.replace(hour=0, minute=0, second=0, microsecond=0)
    trip_end = segments[-1].end
    last_date = (trip_end - timedelta(seconds=1)).date()
    n_days = (last_date - day0.date()).days + 1
    horizon = day0 + timedelta(days=n_days)

    timeline = list(segments)
    if timeline[0].start > day0:
        timeline.insert(0, _pad(day0, timeline[0].start, timeline[0]))
    if timeline[-1].end < horizon:
        timeline.append(_pad(timeline[-1].end, horizon, timeline[-1]))

    logs = []
    for i in range(n_days):
        d0 = day0 + timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        segs, remarks = [], []
        minutes = {OFF: 0, SLEEPER: 0, DRIVING: 0, ON_DUTY: 0}
        miles_today = 0.0
        prev_status = None

        for s in timeline:
            if s.end <= d0 or s.start >= d1:
                continue
            cs, ce = max(s.start, d0), min(s.end, d1)
            a = round((cs - d0).total_seconds() / 60)
            b = round((ce - d0).total_seconds() / 60)
            if b <= a:
                continue
            frac = (ce - cs) / (s.end - s.start)
            seg_miles = s.miles * frac
            miles_today += seg_miles
            minutes[s.status] += b - a
            segs.append({
                "status": s.status,
                "start_minute": a,
                "end_minute": b,
                "kind": s.kind,
                "note": s.note,
                "location": s.location,
                "lat": s.lat,
                "lng": s.lng,
                "miles": round(seg_miles, 1),
            })
            if s.status != prev_status:
                remarks.append({
                    "minute": a,
                    "status": s.status,
                    "location": s.location,
                    "note": s.note,
                })
            prev_status = s.status

        hours = {k: round(v / 60, 2) for k, v in minutes.items()}
        diff = round(24 - sum(hours.values()), 2)
        if diff:  # fix 0.01 rounding drift on the biggest bucket
            biggest = max(hours, key=hours.get)
            hours[biggest] = round(hours[biggest] + diff, 2)

        logs.append({
            "date": d0.date().isoformat(),
            "day_number": i + 1,
            "total_miles_driving": round(miles_today, 1),
            "segments": segs,
            "remarks": remarks,
            "totals_minutes": minutes,
            "totals_hours": hours,
        })
    return logs
