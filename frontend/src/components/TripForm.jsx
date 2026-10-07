import { useRef, useState } from "react";
import { suggest } from "../api";

function PlaceInput({ id, label, value, onChange, onPick, placeholder }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const timer = useRef();
  const ctl = useRef();

  function handle(e) {
    const v = e.target.value;
    onChange(v);
    clearTimeout(timer.current);
    if (v.trim().length < 3) { setItems([]); setOpen(false); return; }
    timer.current = setTimeout(async () => {
      ctl.current?.abort();
      ctl.current = new AbortController();
      try {
        const r = await suggest(v.trim(), ctl.current.signal);
        setItems(r); setOpen(r.length > 0); setActive(-1);
      } catch (err) { /* aborted or offline: keep typing */ }
    }, 350);
  }
  function pick(p) { onPick(p); setOpen(false); }
  function onKey(e) {
    if (!open) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(items[active]); }
    else if (e.key === "Escape") setOpen(false);
  }

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id} value={value} onChange={handle} onKeyDown={onKey} onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder} autoComplete="off" role="combobox" aria-expanded={open}
        aria-controls={`${id}-list`} aria-autocomplete="list" required
      />
      {open && (
        <ul className="suggest" id={`${id}-list`} role="listbox">
          {items.map((p, i) => (
            <li key={p.lat + "," + p.lng + i} role="option" aria-selected={i === active} onMouseDown={() => pick(p)}>
              <strong>{p.label}</strong>
              <span>{p.full_label}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Gauge({ value, onChange }) {
  const cx = 100, cy = 100, r = 80;
  const pt = (f) => {
    const a = Math.PI * (1 - f);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  };
  const f = Math.min(Math.max(value / 70, 0), 1);
  const [ex, ey] = pt(f);
  const hot = value >= 60;
  return (
    <div className="gauge">
      <svg viewBox="0 0 200 118" role="img" aria-label={`${value} of 70 cycle hours used`}>
        <path d={`M${cx - r} ${cy} A${r} ${r} 0 0 1 ${cx + r} ${cy}`} className="g-track" />
        {f > 0 && <path d={`M${cx - r} ${cy} A${r} ${r} 0 0 1 ${ex} ${ey}`} className={hot ? "g-fill hot" : "g-fill"} />}
        <text x={cx} y={cy - 10} textAnchor="middle" className="g-num">{value}</text>
        <text x={cx} y={cy + 12} textAnchor="middle" className="g-sub">of 70 hours used</text>
      </svg>
      <input type="range" min="0" max="70" step="0.5" value={value} onChange={(e) => onChange(Number(e.target.value))} aria-label="Current cycle hours used" />
    </div>
  );
}

const today = () => new Date().toISOString().slice(0, 10);

export default function TripForm({ className, onSubmit, loading, error, details, setDetails }) {
  const [f, setF] = useState({ current: { text: "", place: null }, pickup: { text: "", place: null }, dropoff: { text: "", place: null } });
  const [cycle, setCycle] = useState(0);
  const [start, setStart] = useState(`${today()}T08:00`);

  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const loc = (x) => (x.place && x.place.label === x.text ? { lat: x.place.lat, lng: x.place.lng, label: x.place.label } : x.text.trim());
  const place = (k, label, ph) => (
    <PlaceInput id={k} label={label} placeholder={ph} value={f[k].text}
      onChange={(t) => set(k, { text: t, place: null })} onPick={(p) => set(k, { text: p.label, place: p })} />
  );
  const detail = (k, label, ph) => (
    <div className="field">
      <label htmlFor={`d-${k}`}>{label}</label>
      <input id={`d-${k}`} value={details[k]} placeholder={ph} onChange={(e) => setDetails({ ...details, [k]: e.target.value })} />
    </div>
  );

  function submit(e) {
    e.preventDefault();
    onSubmit({
      current_location: loc(f.current), pickup_location: loc(f.pickup), dropoff_location: loc(f.dropoff),
      current_cycle_used: cycle, start_time: start,
    });
  }

  return (
    <form className={`panel ${className}`} onSubmit={submit}>
      <h1>Plan a trip</h1>
      <p className="lede">Enter the stops and the hours already on your clock. You get the route, every required rest, and a filled daily log for each day.</p>
      {place("current", "Current location", "Where the truck is now")}
      {place("pickup", "Pickup", "Where you load")}
      {place("dropoff", "Drop-off", "Where you deliver")}
      <fieldset>
        <legend>Cycle hours used (70 hour / 8 day)</legend>
        <Gauge value={cycle} onChange={setCycle} />
      </fieldset>
      <div className="field">
        <label htmlFor="start">Trip start (home terminal time)</label>
        <input id="start" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />
      </div>
      <details className="more">
        <summary>Details printed on the log (optional)</summary>
        {detail("carrier", "Carrier name", "John Doe's Transportation")}
        {detail("office", "Main office address", "Washington, DC")}
        {detail("vehicles", "Truck and trailer numbers", "123, 20544")}
        {detail("driver", "Driver name", "John E. Doe")}
        {detail("shipping", "Shipping document or shipper and commodity", "101601")}
      </details>
      {error && <div className="alert" role="alert">{error}</div>}
      <button className="btn primary" type="submit" disabled={loading}>
        {loading ? "Calculating route and hours" : "Calculate trip"}
      </button>
    </form>
  );
}
