import { useState } from "react";
import { fmtDay } from "../utils";
import LogSheet from "./LogSheet";

export default function LogViewer({ className, data, details, recap }) {
  const [day, setDay] = useState(0);
  const idx = Math.min(day, data.logs.length - 1);
  return (
    <section className={`logs ${className}`} aria-label="Daily log sheets">
      <div className="logs-bar no-print">
        <h2>Daily logs</h2>
        <button className="btn ghost" onClick={() => window.print()}>Print or save as PDF</button>
      </div>
      <div className="tabs no-print" role="tablist" aria-label="Log day">
        {data.logs.map((l, i) => (
          <button key={l.date} role="tab" id={`tab-${i}`} aria-selected={i === idx} aria-controls={`sheet-${i}`}
            className={i === idx ? "tab on" : "tab"} onClick={() => setDay(i)}>
            <span>Day {l.day_number}</span><small>{fmtDay(l.date)}</small>
          </button>
        ))}
      </div>
      {data.logs.map((l, i) => (
        <LogSheet key={l.date} id={`sheet-${i}`} labelledBy={`tab-${i}`} active={i === idx}
          log={l} data={data} details={details} recap={recap[i]} />
      ))}
    </section>
  );
}
