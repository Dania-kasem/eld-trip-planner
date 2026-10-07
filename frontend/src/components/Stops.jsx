import { fmtWhen } from "../utils";

const GLYPH = { pickup: "P", dropoff: "D", fuel: "F", break: "B", rest: "Z", restart: "R" };

export default function Stops({ className, data, selected, onSelect }) {
  const steps = data.route.instructions;
  return (
    <section className={`panel ${className}`} aria-label="Stops and rests">
      <h2>Stops and rests</h2>
      <ol className="stops">
        {data.stops.map((s, i) => (
          <li key={i}>
            <button type="button" className={selected === s ? "stop on" : "stop"} onClick={() => onSelect(s)}>
              <span className={`pin pin-${s.type} static`} aria-hidden="true">{GLYPH[s.type]}</span>
              <span className="stop-main">
                <strong>{s.label}</strong>
                <span>{s.location}</span>
                <span className="muted">{fmtWhen(s.start)} for {s.duration_minutes >= 120 ? `${Math.round(s.duration_minutes / 6) / 10} h` : `${s.duration_minutes} min`}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <details className="more">
        <summary>Turn-by-turn route ({steps.length} steps)</summary>
        <ol className="steps">
          {steps.map((st, i) => (
            <li key={i}>
              {(i === 0 || steps[i - 1].leg !== st.leg) && <h3>{st.leg === 0 ? "To pickup" : "Pickup to drop-off"}</h3>}
              <span>{st.text}</span> <span className="muted">{st.miles} mi</span>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}
