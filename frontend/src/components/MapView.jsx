import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import { fmtWhen } from "../utils";

const GLYPH = { start: "S", pickup: "P", dropoff: "D", fuel: "F", break: "B", rest: "Z", restart: "R" };
const icon = (t, on) =>
  L.divIcon({ className: "", html: `<span class="pin pin-${t}${on ? " on" : ""}">${GLYPH[t]}</span>`, iconSize: [32, 32], iconAnchor: [16, 16] });

function Fit({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (!bounds) return;
    map.invalidateSize();
    map.fitBounds(bounds, { padding: [48, 48] });
  }, [bounds, map]);
  return null;
}
function Resize() {
  const map = useMap();
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [map]);
  return null;
}
function Fly({ sel }) {
  const map = useMap();
  useEffect(() => { if (sel) map.flyTo([sel.lat, sel.lng], Math.max(map.getZoom(), 9), { duration: 0.6 }); }, [sel, map]);
  return null;
}

export default function MapView({ className, data, theme, selected, loading }) {
  const geom = data?.route.geometry;
  const bounds = useMemo(() => (geom ? L.latLngBounds(geom) : null), [geom]);
  const start = data?.waypoints.current;

  return (
    <section className={`mapbox ${className}`} aria-label="Route map">
      <MapContainer center={[39.5, -98.35]} zoom={4} scrollWheelZoom className="map">
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
        {geom && (
          <>
            <Polyline positions={geom} pathOptions={{ color: "#ffffff", weight: 10, opacity: 0.95 }} />
            <Polyline positions={geom} pathOptions={{ color: "#C46A00", weight: 5 }} />
          </>
        )}
        {start && (
          <Marker position={[start.lat, start.lng]} icon={icon("start")}>
            <Popup><strong>Start</strong><br />{start.label}</Popup>
          </Marker>
        )}
        {data?.stops.map((s, i) => (
          <Marker key={i} position={[s.lat, s.lng]} icon={icon(s.type, selected === s)}>
            <Popup>
              <strong>{s.label}</strong><br />{s.location}<br />{fmtWhen(s.start)}, {s.duration_minutes} min
            </Popup>
          </Marker>
        ))}
        <Resize />
        <Fit bounds={bounds} />
        <Fly sel={selected} />
      </MapContainer>
      {!data && !loading && <div className="map-hint">Your route and stops appear here.</div>}
      {loading && (
        <div className="map-loading" role="status">
          <div className="road"><span className="truck" aria-hidden="true">&#128666;</span></div>
          Finding the route and checking every duty limit
        </div>
      )}
    </section>
  );
}
