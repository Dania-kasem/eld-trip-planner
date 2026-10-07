import { fmtMin, fmtNum } from "../utils";

const ROWS = [
  ["off_duty", "Off Duty"],
  ["sleeper", "Sleeper Berth"],
  ["driving", "Driving"],
  ["on_duty", "On Duty (not driving)"],
];
const X0 = 100, HW = 36, TOP = 26, RH = 36, RIGHT = 80;
const GW = HW * 24, W = X0 + GW + RIGHT, GB = TOP + RH * 4, H = GB + 100;
const X = (m) => X0 + (m / 60) * HW;
const Y = (r) => TOP + r * RH + RH / 2;
const hourLabel = (h) => (h === 0 || h === 24 ? "Mid" : h === 12 ? "Noon" : String(h % 12));
const clip = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

function Fld({ label, value, grow = 1 }) {
  return (
    <div className="fld" style={{ flex: grow }}>
      <span className="fld-val">{value || "\u00A0"}</span>
      <span className="fld-lab">{label}</span>
    </div>
  );
}

export default function LogSheet({ id, labelledBy, active, log, data, details, recap }) {
  const [y, m, d] = log.date.split("-");
  const rowOf = Object.fromEntries(ROWS.map(([k], i) => [k, i]));
  const pts = log.segments.flatMap((s) => [
    [X(s.start_minute), Y(rowOf[s.status])],
    [X(s.end_minute), Y(rowOf[s.status])],
  ]);
  const ticks = ROWS.map((_, r) => {
    let p = "";
    for (let q = 1; q < 96; q++) {
      if (q % 4 === 0) continue;
      p += `M${X(q * 15)} ${TOP + r * RH}v${q % 2 === 0 ? RH * 0.5 : RH * 0.28}`;
    }
    return p;
  });
  const marks = log.remarks.filter((r) => r.note !== "Off duty");
  const hrs = log.totals_hours;
  const summary = ROWS.map(([k, l]) => `${l} ${fmtNum(hrs[k])} hours`).join(", ");
  const w = data.waypoints;

  return (
    <div className={active ? "sheet-wrap is-active" : "sheet-wrap"} id={id} role="tabpanel" aria-labelledby={labelledBy}>
      <article className="sheet">
        <header className="sheet-head">
          <div>
            <h3>Drivers Daily Log</h3>
            <span className="sheet-sub">(24 hours)</span>
          </div>
          <div className="sheet-date">
            <Fld label="(month)" value={m} />
            <Fld label="(day)" value={d} />
            <Fld label="(year)" value={y} />
          </div>
          <p className="sheet-orig">Original: file at home terminal.<br />Duplicate: driver retains in his/her possession for 8 days.</p>
        </header>

        <div className="sheet-row">
          <Fld label="From" value={w.current.label} grow={2} />
          <Fld label="To" value={w.dropoff.label} grow={2} />
        </div>
        <div className="sheet-row">
          <Fld label="Total miles driving today" value={fmtNum(log.total_miles_driving)} />
          <Fld label="Name of carrier" value={details.carrier} grow={2} />
        </div>
        <div className="sheet-row">
          <Fld label="Truck/tractor and trailer numbers" value={details.vehicles} />
          <Fld label="Main office address" value={details.office} grow={2} />
        </div>

        <div className="graph-scroll">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Duty status graph for ${log.date}. ${summary}.`} overflow="visible">
            {Array.from({ length: 25 }, (_, h) => (
              <text key={h} x={X(h * 60)} y={TOP - 9} textAnchor="middle" className="s-hour">{hourLabel(h)}</text>
            ))}
            <rect x={X0} y={TOP} width={GW} height={RH * 4} className="s-box" />
            {Array.from({ length: 23 }, (_, h) => (
              <line key={h} x1={X((h + 1) * 60)} x2={X((h + 1) * 60)} y1={TOP} y2={GB} className="s-grid" />
            ))}
            {ROWS.map(([k, label], r) => (
              <g key={k}>
                {r > 0 && <line x1={X0} x2={X0 + GW} y1={TOP + r * RH} y2={TOP + r * RH} className="s-box" />}
                <path d={ticks[r]} className="s-tick" />
                <text x={X0 - 8} y={Y(r) + (label.includes(" (") ? -1 : 4)} textAnchor="end" className="s-lab">
                  {label.split(" (")[0]}
                  {label.includes(" (") && <tspan x={X0 - 8} dy="12">{"(" + label.split(" (")[1]}</tspan>}
                </text>
                <text x={X0 + GW + 12} y={Y(r) + 5} className="s-total">{fmtNum(hrs[k])}</text>
              </g>
            ))}
            <line x1={X0 + GW + 8} x2={X0 + GW + 64} y1={GB + 6} y2={GB + 6} className="s-box" />
            <text x={X0 + GW + 12} y={GB + 24} className="s-total">= 24</text>
            <polyline points={pts.map((p) => p.join(",")).join(" ")} className="s-line" />
            {log.segments.map((s, i) => (
              <rect key={i} x={X(s.start_minute)} y={TOP + rowOf[s.status] * RH} width={X(s.end_minute) - X(s.start_minute)} height={RH} fill="transparent">
                <title>{`${s.note}, ${fmtMin(s.start_minute)} to ${fmtMin(s.end_minute === 1440 ? 1440 : s.end_minute)}${s.location ? ", " + s.location : ""}`}</title>
              </rect>
            ))}
            <text x={X0 - 8} y={GB + 20} textAnchor="end" className="s-lab">Remarks</text>
            {marks.map((r, i) => {
              const prev = marks[i - 1];
              const dup = prev && prev.location === r.location && r.minute - prev.minute < 120;
              return (
                <g key={i}>
                  <path d={`M${X(r.minute)} ${GB + 4}v10`} className="s-line thin" />
                  {!dup && (
                    <text transform={`translate(${X(r.minute) + 3} ${GB + 26}) rotate(45)`} className="s-remark">{clip(r.location || r.note, 24)}</text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        <table className="remarks">
          <caption>Remarks: where each duty status changed</caption>
          <thead><tr><th scope="col">Time</th><th scope="col">Status</th><th scope="col">Location and note</th></tr></thead>
          <tbody>
            {log.remarks.map((r, i) => (
              <tr key={i}>
                <td>{fmtMin(r.minute)}</td>
                <td>{ROWS.find(([k]) => k === r.status)[1]}</td>
                <td>{r.location}{r.location ? ", " : ""}{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="sheet-row">
          <Fld label="Shipping documents (DVL or manifest no.) or shipper and commodity" value={details.shipping} />
        </div>

        <table className="recap">
          <caption>Recap: 70 hour / 8 day drivers</caption>
          <tbody>
            <tr><th scope="row">On duty hours today (lines 3 and 4)</th><td>{fmtNum(hrs.driving + hrs.on_duty)}</td></tr>
            <tr><th scope="row">A. Total hours on duty in the last 8 days, including today</th><td>{fmtNum(recap.A)}</td></tr>
            <tr><th scope="row">B. Total hours available tomorrow (70 minus A)</th><td>{fmtNum(recap.B)}</td></tr>
          </tbody>
        </table>
        {recap.restarted && <p className="sheet-foot">*A 34 consecutive hour restart was taken, so the 70 hour clock started again at zero.</p>}
      </article>
    </div>
  );
}
