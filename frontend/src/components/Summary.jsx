import { fmtDur, fmtWhen } from "../utils";

export default function Summary({ className, data }) {
  const s = data.summary;
  const stat = (num, label) => (
    <div className="stat"><div className="num">{num}</div><div className="lab">{label}</div></div>
  );
  return (
    <section className={className} aria-label="Trip summary">
      <div className="stats">
        {stat(`${Math.round(s.total_miles).toLocaleString()} mi`, "Total distance")}
        {stat(fmtDur(s.total_driving_hours), "Driving time")}
        {stat(s.log_days, s.log_days === 1 ? "Log day" : "Log days")}
        {stat(fmtWhen(s.end), "Arrival")}
      </div>
      <details className="note">
        <summary>Assumptions behind the plan</summary>
        <ul>{data.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </details>
    </section>
  );
}
