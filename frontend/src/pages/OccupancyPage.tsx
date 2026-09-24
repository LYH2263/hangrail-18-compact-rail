import { useEffect, useState } from "react";
import { api } from "../api/client";
type Rail = { id: number; label: string; length_cm: number };
type Seg = { ticket_code: string; garment_name: string; start_cm: number; end_cm: number };
type Occ = { rail_id: number; label: string; length_cm: number; segments: Seg[] };
export default function OccupancyPage() {
  const [rails, setRails] = useState<Rail[]>([]);
  const [maps, setMaps] = useState<Occ[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [note, setNote] = useState<Record<number, { ok: boolean; text: string }>>({});
  async function loadMaps(rs: Rail[]) {
    const all = await Promise.all(rs.map(r => api<Occ>(`/occupancy/${r.id}`)));
    setMaps(all);
  }
  useEffect(() => {
    api<Rail[]>("/rails").then(rs => {
      setRails(rs);
      loadMaps(rs);
    });
  }, []);
  async function compact(id: number, label: string) {
    setBusy(id); setNote(n => ({ ...n, [id]: { ok: true, text: "" } }));
    try {
      await api<Occ>(`/rails/${id}/compact`, { method: "POST" });
      const rs = await api<Rail[]>("/rails");
      setRails(rs);
      await loadMaps(rs);
      setNote(n => ({ ...n, [id]: { ok: true, text: `${label} 已紧凑，尺线连续无空洞` } }));
    } catch (e) {
      setNote(n => ({ ...n, [id]: { ok: false, text: e instanceof Error ? e.message : String(e) } }));
    } finally {
      setBusy(null);
    }
  }
  return (<>
    <h2>占位图（横向尺线）</h2>
    {maps.map(m => (
      <div className="ruler-wrap" key={m.rail_id}>
        <div className="ruler-label">
          <span>{m.label}</span>
          <span className="mono">0 — {m.length_cm} cm</span>
        </div>
        <div className="ruler">
          {m.segments.map((s, i) => (
            <div key={i} className="seg" style={{ left: `${(s.start_cm / m.length_cm) * 100}%`, width: `${((s.end_cm - s.start_cm) / m.length_cm) * 100}%` }}
              title={`${s.ticket_code} ${s.start_cm}-${s.end_cm}cm`}>
              {s.garment_name}
            </div>
          ))}
        </div>
        <div className="toolbar">
          <button disabled={busy === m.rail_id} onClick={() => compact(m.rail_id, m.label)}>
            {busy === m.rail_id ? "紧凑中…" : "紧凑重排本杆"}
          </button>
          {note[m.rail_id]?.text &&
            <span className={note[m.rail_id].ok ? "ok" : "err"}>{note[m.rail_id].text}</span>}
        </div>
      </div>
    ))}
    {!rails.length && <p>暂无挂杆</p>}
  </>);
}
