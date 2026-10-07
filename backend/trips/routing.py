"""
Free map services used by the API:

* Nominatim (OpenStreetMap)  -> geocoding / reverse geocoding
* OSRM public demo server    -> driving route, distance, turn-by-turn steps

Both can be swapped for self-hosted instances via env vars NOMINATIM_URL and
OSRM_URL.
"""
from __future__ import annotations

import bisect
import math
import os
import time
from functools import lru_cache

import requests

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
USER_AGENT = os.environ.get("HTTP_USER_AGENT", "eld-trip-planner/1.0 (assessment project)")
METERS_PER_MILE = 1609.344


class RoutingError(Exception):
    """Raised when geocoding or routing fails (maps to HTTP 400/502)."""


def _get(url: str, params: dict, timeout: int = 20) -> dict | list:
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise RoutingError(f"Map service request failed: {exc}") from exc


# --------------------------------------------------------------------------- #
# Geocoding
# --------------------------------------------------------------------------- #
def short_name(item: dict) -> str:
    """'City, ST' style label from a Nominatim result."""
    addr = item.get("address", {}) or {}
    place = (
        addr.get("city") or addr.get("town") or addr.get("village")
        or addr.get("hamlet") or addr.get("municipality") or addr.get("county")
        or item.get("name") or ""
    )
    iso = addr.get("ISO3166-2-lvl4", "")
    state = iso.split("-")[-1] if iso.startswith("US-") else (addr.get("state") or addr.get("country") or "")
    label = ", ".join(p for p in (place, state) if p)
    return label or item.get("display_name", "Unknown")


def search(query: str, limit: int = 5) -> list[dict]:
    data = _get(
        f"{NOMINATIM_URL}/search",
        {"q": query, "format": "jsonv2", "limit": limit, "addressdetails": 1},
    )
    return [
        {
            "label": short_name(d),
            "full_label": d.get("display_name", ""),
            "lat": float(d["lat"]),
            "lng": float(d["lon"]),
        }
        for d in data
    ]


@lru_cache(maxsize=256)
def geocode(query: str) -> tuple:
    results = search(query, limit=1)
    if not results:
        raise RoutingError(f"Could not find location: '{query}'")
    r = results[0]
    return (r["lat"], r["lng"], r["label"])


class Reverser:
    """
    Reverse geocoder that respects Nominatim's 1 request/second policy and a
    total time budget, so a request can never hang. Falls back to coordinates.
    """

    def __init__(self, budget_seconds: float = 20.0, enabled: bool = True):
        self.enabled = enabled
        self.deadline = time.monotonic() + budget_seconds
        self.last_call = 0.0
        self.cache: dict[tuple, str] = {}

    def name(self, lat: float, lng: float) -> str:
        key = (round(lat, 2), round(lng, 2))
        if key in self.cache:
            return self.cache[key]
        fallback = f"{lat:.2f}, {lng:.2f}"
        if not self.enabled or time.monotonic() > self.deadline:
            return fallback
        wait = 1.05 - (time.monotonic() - self.last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            self.last_call = time.monotonic()
            data = _get(
                f"{NOMINATIM_URL}/reverse",
                {"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 10, "addressdetails": 1},
                timeout=8,
            )
            label = short_name(data) if isinstance(data, dict) and "address" in data else fallback
        except RoutingError:
            label = fallback
        self.cache[key] = label
        return label


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #
_VERBS = {
    "turn": "Turn {mod} onto",
    "end of road": "At end of road turn {mod} onto",
    "fork": "Keep {mod} onto",
    "merge": "Merge {mod} onto",
    "on ramp": "Take the ramp onto",
    "off ramp": "Take the exit onto",
    "new name": "Continue onto",
    "continue": "Continue onto",
    "roundabout": "Take the roundabout onto",
    "rotary": "Take the rotary onto",
    "exit roundabout": "Exit the roundabout onto",
}


def _instruction(step: dict) -> str:
    man = step.get("maneuver", {})
    kind, mod = man.get("type", ""), man.get("modifier", "")
    name = step.get("name") or "the road"
    if kind == "depart":
        return f"Depart on {name}"
    if kind == "arrive":
        return "Arrive at destination"
    verb = _VERBS.get(kind, "Continue onto").format(mod=mod)
    return f"{verb} {name}".replace("  ", " ")


def osrm_route(points: list[tuple]) -> dict:
    """points: [(lat, lng), ...] -> distances, durations, geometry, steps."""
    coords = ";".join(f"{lng},{lat}" for lat, lng in points)
    data = _get(
        f"{OSRM_URL}/route/v1/driving/{coords}",
        {"overview": "full", "geometries": "geojson", "steps": "true"},
        timeout=40,
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError("No drivable route found between those locations.")
    route = data["routes"][0]

    legs, instructions = [], []
    for li, leg in enumerate(route["legs"]):
        legs.append({"miles": leg["distance"] / METERS_PER_MILE, "seconds": leg["duration"]})
        for step in leg.get("steps", []):
            kind = step.get("maneuver", {}).get("type", "")
            name = step.get("name") or ""
            miles = step["distance"] / METERS_PER_MILE
            prev = instructions[-1] if instructions else None
            if prev and prev["leg"] == li and kind in ("continue", "new name") and prev["_name"] == name:
                prev["miles"] += miles
                continue
            instructions.append({"leg": li, "text": _instruction(step), "miles": miles, "_name": name})
    for ins in instructions:
        ins["miles"] = round(ins["miles"], 1)
        ins.pop("_name")

    geometry = [[lat, lng] for lng, lat in route["geometry"]["coordinates"]]
    return {
        "legs": legs,
        "miles": route["distance"] / METERS_PER_MILE,
        "geometry": geometry,
        "instructions": instructions,
    }


def downsample(geometry: list, max_points: int = 1500) -> list:
    if len(geometry) <= max_points:
        return geometry
    step = math.ceil(len(geometry) / max_points)
    out = geometry[::step]
    if out[-1] != geometry[-1]:
        out.append(geometry[-1])
    return out


# --------------------------------------------------------------------------- #
# Position along the route
# --------------------------------------------------------------------------- #
def _haversine(a: list, b: list) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


class RouteLocator:
    """Maps a trip mile marker to (lat, lng, label)."""

    def __init__(self, geometry: list, total_miles: float, anchors: list[tuple], reverser: Reverser):
        """anchors: [(mile, lat, lng, label), ...] known places (start/pickup/dropoff)."""
        self.geometry = geometry
        self.total_miles = max(total_miles, 1e-9)
        self.anchors = anchors
        self.reverser = reverser
        self.cum = [0.0]
        for i in range(1, len(geometry)):
            self.cum.append(self.cum[-1] + _haversine(geometry[i - 1], geometry[i]))

    def coords(self, mile: float) -> tuple:
        target = min(max(mile / self.total_miles, 0.0), 1.0) * self.cum[-1]
        i = bisect.bisect_left(self.cum, target)
        if i <= 0:
            return tuple(self.geometry[0])
        if i >= len(self.geometry):
            return tuple(self.geometry[-1])
        seg = self.cum[i] - self.cum[i - 1] or 1e-9
        f = (target - self.cum[i - 1]) / seg
        a, b = self.geometry[i - 1], self.geometry[i]
        return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)

    def locate(self, mile: float) -> tuple:
        for a_mile, lat, lng, label in self.anchors:
            if abs(mile - a_mile) < 0.5:
                return lat, lng, label
        lat, lng = self.coords(mile)
        return lat, lng, self.reverser.name(lat, lng)
