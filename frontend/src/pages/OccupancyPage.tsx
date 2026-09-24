import { useEffect, useState } from "react";
import { api } from "../api/client";
type Rail = { id: number; label: string; length_cm: number };
type Occ = { rail_id: number; label: string; length_cm: number; segments: { ticket_code: string; garment_name: string; start_cm: number; end_cm: number }[] };
type Busy = Record<number, boolean>;
type Note = { ok: boolean; text: string };
export default function OccupancyPage() {
  const [rails, setRails] = useState<Rail[]>([]);
  const [maps, setMaps] = useState<Occ[]>([]);
  const [busy, setBusy] = useState<Busy>({});
  const [notes, setNotes] = useState<Record<number, Note>>({});
  function load() {
    return api<Rail[]>("/rails").then(async rs => {
      setRails(rs);
      const all = await Promise.all(rs.map(r => api<Occ>(`/occupancy/${r.id}`)));
      setMaps(all);
    });
  }
  useEffect(() => { load().catch(() => setRails([])); }, []);
  async function compactRail(id: number) {
    setBusy(b => ({ ...b, [id]: true }));
    setNotes(n => ({ ...n, [id]: { ok: true, text: "" } }));
    try {
      const out = await api<Occ>(`/rails/${id}/compact`, { method: "POST" });
      setMaps(ms => ms.map(m => (m.rail_id === id ? out : m)));
      const used = out.segments.length ? out.segments[out.segments.length - 1].end_cm : 0;
      setNotes(n => ({ ...n, [id]: { ok: true, text: `已紧凑：${out.segments.length} 件贴齐 0–${used}cm，尺线无空洞` } }));
      window.dispatchEvent(new Event("hangrail:occupancy-changed"));
    } catch (e) {
      setNotes(n => ({ ...n, [id]: { ok: false, text: e instanceof Error ? e.message : String(e) } }));
    } finally {
      setBusy(b => ({ ...b, [id]: false }));
    }
  }
  return (<>
    <h2>占位图（横向尺线）</h2>
    {maps.map(m => (
      <div className="ruler-wrap" key={m.rail_id}>
        <div className="ruler-label">
          <span>{m.label}</span>
          <span className="ruler-actions">
            <span className="mono">0 — {m.length_cm} cm</span>
            <button className="compact-btn" disabled={!!busy[m.rail_id] || m.segments.length === 0}
              onClick={() => compactRail(m.rail_id)}>
              {busy[m.rail_id] ? "紧凑中…" : "紧凑本杆"}
            </button>
          </span>
        </div>
        <div className="ruler">
          {m.segments.map((s, i) => (
            <div key={i} className="seg" style={{ left: `${(s.start_cm / m.length_cm) * 100}%`, width: `${((s.end_cm - s.start_cm) / m.length_cm) * 100}%` }}
              title={`${s.ticket_code} ${s.start_cm}-${s.end_cm}cm`}>
              {s.garment_name}
            </div>
          ))}
        </div>
        {notes[m.rail_id]?.text &&
          <div className={notes[m.rail_id].ok ? "ok compact-note" : "err compact-note"}>{notes[m.rail_id].text}</div>}
      </div>
    ))}
    {!rails.length && <p>暂无挂杆</p>}
  </>);
}
