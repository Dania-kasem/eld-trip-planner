import { useEffect, useMemo, useState } from "react";
import { planTrip, wakeServer } from "./api";
import { useTheme } from "./useTheme";
import { cycleRecap } from "./utils";
import TripForm from "./components/TripForm";
import Summary from "./components/Summary";
import MapView from "./components/MapView";
import Stops from "./components/Stops";
import LogViewer from "./components/LogViewer";

export default function App() {
  const { theme, toggle } = useTheme();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState({ carrier: "", office: "", vehicles: "", driver: "", shipping: "" });
  useEffect(() => { wakeServer(); }, []);
  const recap = useMemo(() => (data ? cycleRecap(data.logs, data.summary.cycle_used_start) : []), [data]);

  async function submit(payload) {
    setLoading(true);
    setError("");
    setSelected(null);
    try {
      setData(await planTrip(payload));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <header className="topbar no-print">
        <div className="brand">
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
            <rect x="1" y="1" width="26" height="26" rx="6" fill="var(--accent)" />
            <path d="M5 19h18M5 14h18M5 9h18" stroke="var(--on-accent)" strokeWidth="2" strokeDasharray="5 3" />
          </svg>
          <span>ELD Trip Planner</span>
        </div>
        <button className="btn ghost" onClick={toggle} aria-pressed={theme === "dark"}>
          {theme === "dark" ? "Light theme" : "Dark theme"}
        </button>
      </header>

      <main className={data ? "layout has-data" : "layout"}>
        <TripForm className="a-form no-print" onSubmit={submit} loading={loading} error={error} details={details} setDetails={setDetails} />
        {data && <Summary className="a-summary no-print" data={data} />}
        <MapView className="a-map no-print" data={data} theme={theme} selected={selected} loading={loading} />
        {data && <Stops className="a-stops no-print" data={data} selected={selected} onSelect={setSelected} />}
        {data && <LogViewer className="a-log" data={data} details={details} recap={recap} />}
      </main>
    </>
  );
}
