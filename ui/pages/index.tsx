// ui/pages/index.tsx
import * as React from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type LogSetter = React.Dispatch<React.SetStateAction<string[]>>;

async function streamGET(url: string, setLogs: LogSetter, setRunning: (b: boolean) => void) {
    setLogs((l) => [...l, `--- streaming: GET ${url}`]);
    try {
        const resp = await fetch(url);
        if (!resp.ok || !resp.body) {
            setLogs((l) => [...l, `HTTP ${resp.status}`]);
            return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            for (const line of chunk.split("\n")) {
                if (!line.trim()) continue;
                try {
                    const obj = JSON.parse(line);
                    if (obj?.line) setLogs((l) => [...l, obj.line]);
                    else setLogs((l) => [...l, line]);
                } catch {
                    setLogs((l) => [...l, line]);
                }
            }
        }
    } catch (e: any) {
        setLogs((l) => [...l, `Error: ${e?.message || e}`]);
    } finally {
        setRunning(false);
    }
}

function Box({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16, marginBottom: 16, background: "#fff" }}>
            <h2 style={{ marginTop: 0, color: "#111" }}>{title}</h2>
            {children}
        </div>
    );
}

function LogPane({ logs }: { logs: string[] }) {
    return (
        <div
            style={{
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: 12,
                background: "#0b1020",
                color: "#dbeafe",
                padding: 12,
                borderRadius: 8,
                minHeight: 180,
                maxHeight: 420,
                overflow: "auto",
                whiteSpace: "pre-wrap",
            }}
        >
            {logs.map((l, i) => (
                <div key={i}>{l}</div>
            ))}
        </div>
    );
}

/** Plan preview (optional helper) */
function PlanPreviewBox() {
    const [issueKey, setIssueKey] = React.useState("");
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const [data, setData] = React.useState<any | null>(null);

    const act = async () => {
        setLoading(true);
        setError(null);
        setData(null);
        try {
            const qs = new URLSearchParams({ issue_key: issueKey.trim() });
            const resp = await fetch(`${apiBase}/plan/preview?${qs.toString()}`);
            if (!resp.ok) {
                const t = await resp.text();
                throw new Error(t || `HTTP ${resp.status}`);
            }
            const json = await resp.json();
            if (json.error) throw new Error(json.error);
            setData(json);
        } catch (e: any) {
            setError(e?.message || String(e));
        } finally {
            setLoading(false);
        }
    };

    const Section = ({ title, children }: any) => (
        <div style={{ margin: "12px 0" }}>
            <div style={{ fontWeight: 700, marginBottom: 6, color: "#111" }}>{title}</div>
            <div style={{ color: "#111", lineHeight: 1.5 }}>{children}</div>
        </div>
    );

    const List = ({ items }: { items: string[] }) => (
        <ul style={{ margin: "6px 0 0 18px", color: "#111" }}>
            {items?.map((x, i) => (
                <li key={i}>{x}</li>
            ))}
        </ul>
    );

    return (
        <Box title="🧭 Plan Preview (AC-aware)">
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-123)"
                    style={{ flex: 1, minWidth: 240, padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
                />
                <button disabled={!issueKey || loading} onClick={act} style={{ padding: "8px 12px" }}>
                    {loading ? "Generating…" : "Generate Plan"}
                </button>
            </div>

            {error && <div style={{ color: "#b91c1c" }}>{error}</div>}

            {data && (
                <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                    <div style={{ fontSize: 14, color: "#111" }}>
                        <div><strong>Issue:</strong> {data.issue_key}</div>
                        <div><strong>Summary:</strong> {data.summary || "(no title)"}</div>
                        <div><strong>Suggested module:</strong> <code style={{ color: "#111" }}>{data.suggested_module_name}</code></div>
                    </div>
                    {data.description_md && (
                        <Section title="Description">
              <pre style={{ whiteSpace: "pre-wrap", margin: 0, background: "#fff", color: "#111", padding: 0 }}>
                {data.description_md}
              </pre>
                            {data.description_checklist?.length ? <List items={data.description_checklist} /> : null}
                        </Section>
                    )}
                    {data.acceptance_md && (
                        <Section title="Acceptance Criteria">
              <pre style={{ whiteSpace: "pre-wrap", margin: 0, background: "#fff", color: "#111", padding: 0 }}>
                {data.acceptance_md}
              </pre>
                            {data.acceptance_checklist?.length ? <List items={data.acceptance_checklist} /> : null}
                        </Section>
                    )}
                    <Section title="Suggested Plan"><List items={data.suggested_plan || []} /></Section>
                    <Section title="Validations (CI expectations)"><List items={data.validations || []} /></Section>
                    <Section title="Risks / Guardrails"><List items={data.risks || []} /></Section>
                </div>
            )}
        </Box>
    );
}

/** 🚀 One-Shot (CLI passthrough) – MR → Review/Merge → Deploy → QA */
function OneShotCLITile() {
    const [issueKey, setIssueKey] = React.useState("");
    const [running, setRunning] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        const qs = new URLSearchParams({ issue_key: issueKey.trim() });
        await streamGET(`${apiBase}/stream/one-shot?${qs.toString()}`, setLogs, setRunning);
    };

    return (
        <Box title="🚀 One-Shot: Jira → MR → Review/Merge → Deploy → QA">
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap", color: "#111" }}>
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-123)"
                    style={{ flex: 1, minWidth: 240, padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
                />
                <button disabled={!issueKey || running} onClick={act} style={{ padding: "8px 12px" }}>
                    {running ? "Running…" : "Run One-Shot"}
                </button>
            </div>
            <LogPane logs={logs} />
        </Box>
    );
}

/** STEP 1: Open MR (copilot-workflow) */
function Step1WorkflowTile() {
    const [issueKey, setIssueKey] = React.useState("");
    const [running, setRunning] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        const qs = new URLSearchParams({ issue_key: issueKey.trim() });
        await streamGET(`${apiBase}/stream/workflow-cli?${qs.toString()}`, setLogs, setRunning);
    };

    return (
        <Box title="Step 1 — Open MR (copilot-workflow)">
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap", color: "#111" }}>
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-104)"
                    style={{ flex: 1, minWidth: 240, padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
                />
                <button disabled={!issueKey || running} onClick={act} style={{ padding: "8px 12px" }}>
                    {running ? "Running…" : "Run copilot-workflow"}
                </button>
            </div>
            <LogPane logs={logs} />
        </Box>
    );
}

/** STEP 2: Review/Merge/Deploy (copilot-ai-review-merge) */
function Step2ReviewMergeDeployTile() {
    const [mrUrl, setMrUrl] = React.useState("");
    const [autoMerge, setAutoMerge] = React.useState(true);
    const [deploy, setDeploy] = React.useState(true);
    const [verbose, setVerbose] = React.useState(true);
    const [running, setRunning] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        const qs = new URLSearchParams({
            mr_url: mrUrl.trim(),
            auto_merge: String(autoMerge),
            deploy: String(deploy),
            verbose: String(verbose),
        });
        await streamGET(`${apiBase}/stream/ai-review-merge-cli?${qs.toString()}`, setLogs, setRunning);
    };

    return (
        <Box title="Step 2 — Review / Merge / Deploy (copilot-ai-review-merge)">
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap", color: "#111" }}>
                <input
                    value={mrUrl}
                    onChange={(e) => setMrUrl(e.target.value)}
                    placeholder="MR URL"
                    style={{ flex: 1, minWidth: 320, padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
                />
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input type="checkbox" checked={autoMerge} onChange={(e) => setAutoMerge(e.target.checked)} />
                    --auto-merge
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input type="checkbox" checked={deploy} onChange={(e) => setDeploy(e.target.checked)} />
                    --deploy
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input type="checkbox" checked={verbose} onChange={(e) => setVerbose(e.target.checked)} />
                    --verbose
                </label>
                <button disabled={!mrUrl || running} onClick={act} style={{ padding: "8px 12px" }}>
                    {running ? "Running…" : "Run ai-review-merge"}
                </button>
            </div>
            <LogPane logs={logs} />
        </Box>
    );
}

/** STEP 3: QA on EC2 (copilot-qa-ec2) */
function Step3QATile() {
    const [issueKey, setIssueKey] = React.useState("");
    const [running, setRunning] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        const qs = new URLSearchParams({ issue_key: issueKey.trim() });
        await streamGET(`${apiBase}/stream/qa-ec2-cli?${qs.toString()}`, setLogs, setRunning);
    };

    return (
        <Box title="Step 3 — QA on EC2 (copilot-qa-ec2)">
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap", color: "#111" }}>
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-104)"
                    style={{ flex: 1, minWidth: 240, padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
                />
                <button disabled={!issueKey || running} onClick={act} style={{ padding: "8px 12px" }}>
                    {running ? "Running…" : "Run QA"}
                </button>
            </div>
            <LogPane logs={logs} />
        </Box>
    );
}

export default function Home() {
    return (
        <div style={{ maxWidth: 900, margin: "24px auto", padding: "0 16px", background: "#fafafa" }}>
            <h1 style={{ color: "#111" }}>Drupal DevOps Co-Pilot</h1>
            <p style={{ color: "#374151" }}>
                Run the full flow in one click or step through each stage independently — all with live streaming logs.
            </p>

            {/* One-click */}
            <OneShotCLITile />

            {/* Step-by-step */}
            <Step1WorkflowTile />
            <Step2ReviewMergeDeployTile />
            <Step3QATile />

            {/* Optional helper */}
            <PlanPreviewBox />
        </div>
    );
}
