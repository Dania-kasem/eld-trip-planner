import json
import os
from datetime import date, datetime, time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import hos
from .routing import (
    Reverser, RouteLocator, RoutingError, downsample, geocode, osrm_route, search,
)

MAX_AVG_SPEED_MPH = 60.0   # cap OSRM's car speeds to a realistic truck average

ASSUMPTIONS = [
    "Property-carrying driver on the 70-hour / 8-day schedule; no adverse driving conditions.",
    "Driver starts fully rested (10 consecutive hours off duty just completed).",
    "Hours in 'current cycle used' stay inside the 8-day window for the whole trip.",
    "1 hour on duty (not driving) at pickup and 1 hour at drop-off.",
    "Fuel stop (30 min, on duty) at least every 1,000 miles.",
    "30-minute break after 8 cumulative driving hours; 11-hour driving and 14-hour window limits.",
    "10-hour rests are logged as Sleeper Berth; a 34-hour restart is inserted if the 70-hour limit is reached.",
    f"Average driving speed is the route's estimate capped at {int(MAX_AVG_SPEED_MPH)} mph.",
    "Log days run midnight to midnight in the home-terminal time of the start location.",
]


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def geocode_suggest(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 3:
        return JsonResponse({"results": []})
    try:
        return JsonResponse({"results": search(q, limit=5)})
    except RoutingError as exc:
        return _error(str(exc), 502)


def _resolve_location(value, field):
    """Accepts 'Richmond, VA' or {'lat':..,'lng':..,'label':..}."""
    if isinstance(value, dict) and "lat" in value and "lng" in value:
        try:
            return float(value["lat"]), float(value["lng"]), str(value.get("label") or "Selected location")
        except (TypeError, ValueError):
            raise ValueError(f"'{field}' has invalid coordinates.")
    if isinstance(value, str) and value.strip():
        return geocode(value.strip())
    raise ValueError(f"'{field}' is required.")


def _parse_start(raw):
    if not raw:
        return datetime.combine(date.today(), time(8, 0))
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", ""))
    except ValueError:
        raise ValueError("'start_time' must be an ISO datetime, e.g. 2026-10-05T08:00.")
    return dt.replace(second=0, microsecond=0, tzinfo=None)


def _leg_minutes(miles, seconds):
    if miles <= 0.01 or seconds <= 0:
        return 0.0
    speed = min(miles / (seconds / 3600.0), MAX_AVG_SPEED_MPH)
    return miles / speed * 60.0


@csrf_exempt
@require_POST
def plan_trip_view(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _error("Request body must be valid JSON.")

    try:
        cur = _resolve_location(body.get("current_location"), "current_location")
        pick = _resolve_location(body.get("pickup_location"), "pickup_location")
        drop = _resolve_location(body.get("dropoff_location"), "dropoff_location")
        try:
            cycle_used = float(body.get("current_cycle_used", 0))
        except (TypeError, ValueError):
            raise ValueError("'current_cycle_used' must be a number of hours.")
        if not 0 <= cycle_used <= 70:
            raise ValueError("'current_cycle_used' must be between 0 and 70 hours.")
        start = _parse_start(body.get("start_time"))
    except ValueError as exc:
        return _error(str(exc))
    except RoutingError as exc:
        return _error(str(exc), 400)

    try:
        route = osrm_route([cur[:2], pick[:2], drop[:2]])
    except RoutingError as exc:
        return _error(str(exc), 502)

    leg1, leg2 = route["legs"]
    m1, m2 = leg1["miles"], leg2["miles"]
    total_miles = m1 + m2

    segments = hos.plan_trip(
        m1, _leg_minutes(m1, leg1["seconds"]),
        m2, _leg_minutes(m2, leg2["seconds"]),
        cycle_used, start,
    )

    reverser = Reverser(
        budget_seconds=float(os.environ.get("REVERSE_GEOCODE_BUDGET", 20)),
        enabled=os.environ.get("REVERSE_GEOCODE", "true").lower() == "true",
    )
    locator = RouteLocator(
        route["geometry"], total_miles,
        anchors=[(0.0, *cur), (m1, *pick), (total_miles, *drop)],
        reverser=reverser,
    )
    for seg in segments:
        seg.lat, seg.lng, seg.location = locator.locate(seg.mile)

    logs = hos.build_daily_logs(segments, start)

    stops = [
        {
            "type": s.kind,
            "label": s.note,
            "location": s.location,
            "lat": s.lat,
            "lng": s.lng,
            "start": s.start.isoformat(),
            "end": s.end.isoformat(),
            "duration_minutes": round(s.minutes),
            "mile": round(s.mile, 1),
        }
        for s in segments if s.kind != "drive"
    ]

    drive_hours = sum(s.minutes for s in segments if s.status == hos.DRIVING) / 60
    trip_hours = (segments[-1].end - segments[0].start).total_seconds() / 3600

    return JsonResponse({
        "summary": {
            "total_miles": round(total_miles, 1),
            "miles_to_pickup": round(m1, 1),
            "miles_pickup_to_dropoff": round(m2, 1),
            "total_driving_hours": round(drive_hours, 2),
            "total_trip_hours": round(trip_hours, 2),
            "log_days": len(logs),
            "start": segments[0].start.isoformat(),
            "end": segments[-1].end.isoformat(),
            "cycle_used_start": cycle_used,
        },
        "waypoints": {
            "current": {"lat": cur[0], "lng": cur[1], "label": cur[2]},
            "pickup": {"lat": pick[0], "lng": pick[1], "label": pick[2]},
            "dropoff": {"lat": drop[0], "lng": drop[1], "label": drop[2]},
        },
        "route": {"geometry": downsample(route["geometry"]), "instructions": route["instructions"]},
        "stops": stops,
        "logs": logs,
        "assumptions": ASSUMPTIONS,
    })
