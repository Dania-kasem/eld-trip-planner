const BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api").replace(/\/$/, "");

async function parse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export async function planTrip(payload) {
  try {
    const res = await fetch(`${BASE}/plan-trip/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await parse(res);
  } catch (e) {
    if (e instanceof TypeError) throw new Error("Can't reach the server. Check your connection and try again.");
    throw e;
  }
}

export async function suggest(q, signal) {
  const res = await fetch(`${BASE}/geocode/?q=${encodeURIComponent(q)}`, { signal });
  return (await parse(res)).results;
}

/** Free hosts put idle servers to sleep; a silent ping on page load wakes the API up early. */
export function wakeServer() {
  fetch(`${BASE}/health/`).catch(() => {});
}
