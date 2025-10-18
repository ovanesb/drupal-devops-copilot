// ui/pages/audit.tsx
import * as React from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function AuditPage() {
    const [events, setEvents] = React.useState<any[]>([]);
    const [limit, setLimit] = React.useState(200);
    const [selected, setSelected] = React.useState<any[] | null>(null);
    const [loading, setLoading] = React.useState(false);

    const loadList = async () => {
        setLoading(true);
        try {
            const resp = await fetch(`${apiBase}/audit/list?limit=${limit}`);
            const json = await resp.json();
            setEvents(json.events || []);
        } finally {
            setLoading(false);
        }
    };

    const loadRun = async (runId: string) => {
        setLoading(true);
        try {
            const resp = await fetch(`${apiBase}/audit/run/${runId}`);
            const json = await resp.json();
            setSelected(json.run || []);
        } finally {
            setLoading(false);
        }
    };

    React.useEffect(() => {
        loadList();
    }, []);

    return (
        <div style={{ maxWidth: 1000, margin: "24px auto", padding: "0 16px" }}>
            <h1>Audit Trail</h1>
            <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
                <input
                    value={limit}
                    onChange={(e) => setLimit(parseInt(e.target.value || "200", 10))}
                    style={{ width: 120, padding: 6 }}
                    type="number"
                    min={10}
                    max={1000}
                />
                <button onClick={loadList} disabled={loading}>
                    {loading ? "Loading…" : "Refresh"}
                </button>
            </div>

            <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead style={{ background: "#f3f4f6" }}>
                    <tr>
                        <th style={{ textAlign: "left", padding: 8 }}>Time (UTC)</th>
                        <th style={{ textAlign: "left", padding: 8 }}>Run</th>
                        <th style={{ textAlign: "left", padding: 8 }}>Action</th>
                        <th style={{ textAlign: "left", padding: 8 }}>Status</th>
                        <th style={{ textAlign: "left", padding: 8 }}>Message</th>
                    </tr>
                    </thead>
                    <tbody>
                    {events.map((e, i) => (
                        <tr key={i} style={{ borderTop: "1px solid #eee" }}>
                            <td style={{ padding: 8, whiteSpace: "nowrap" }}>{e.ts}</td>
                            <td style={{ padding: 8 }}>
                                <a href="#" onClick={(ev) => { ev.preventDefault(); loadRun(e.run_id); }}>
                                    {e.run_id}
                                </a>
                            </td>
                            <td style={{ padding: 8 }}>{e.action}</td>
                            <td style={{ padding: 8 }}>{e.status}</td>
                            <td style={{ padding: 8, color: "#374151" }}>{e.message}</td>
                        </tr>
                    ))}
                    {!events.length && (
                        <tr>
                            <td colSpan={5} style={{ padding: 12, textAlign: "center", color: "#6b7280" }}>
                                No events yet.
                            </td>
                        </tr>
                    )}
                    </tbody>
                </table>
            </div>

            {selected && (
                <div style={{ marginTop: 16 }}>
                    <h2>Run details</h2>
                    <pre
                        style={{
                            background: "#0b1020",
                            color: "#dbeafe",
                            padding: 12,
                            borderRadius: 8,
                            maxHeight: 360,
                            overflow: "auto",
                        }}
                    >
            {JSON.stringify(selected, null, 2)}
          </pre>
                </div>
            )}
        </div>
    );
}
