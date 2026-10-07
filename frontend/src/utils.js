export const fmtNum = (n) => String(Number(n.toFixed(2)));

export function fmtDur(hours) {
  const m = Math.round(hours * 60);
  const h = Math.floor(m / 60), r = m % 60;
  if (!h) return `${r} m`;
  return r ? `${h} h ${r} m` : `${h} h`;
}

export function fmtMin(min) {
  const h = Math.floor(min / 60) % 24, m = min % 60;
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`;
}

export const fmtWhen = (iso) =>
  new Date(iso).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" });

export const fmtDay = (iso) =>
  new Date(iso + "T00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

/** Per-day 70h/8d recap: hours on duty today, total in cycle (A), available tomorrow (B). */
export function cycleRecap(logs, startUsed) {
  let run = startUsed;
  return logs.map((log, i) => {
    let today = 0, restarted = false;
    for (const s of log.segments) {
      const h = (s.end_minute - s.start_minute) / 60;
      if (s.status === "driving" || s.status === "on_duty") { run += h; today += h; }
      if (s.kind === "restart") {
        const next = logs[i + 1]?.segments[0];
        if (s.end_minute < 1440 || !(next && next.kind === "restart")) { run = 0; restarted = true; }
      }
    }
    return { today, A: run, B: Math.max(0, 70 - run), restarted };
  });
}
