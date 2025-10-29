// ui/pages/index.tsx
import * as React from "react";
import Header from "../components/Header";
import StatusBadge from "../components/StatusBadge";
import CopyButton from "../components/CopyButton";

const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type LogSetter = React.Dispatch<React.SetStateAction<string[]>>;
type Status = "idle" | "running" | "success" | "error";

async function streamGET(url: string, setLogs: LogSetter, setRunning: (b: boolean) => void, setStatus: (s: Status) => void) {
    setLogs((l) => [...l, `--- streaming: GET ${url}`]);
    setStatus("running");
    let hasError = false;
    try {
        const resp = await fetch(url);
        if (!resp.ok || !resp.body) {
            setLogs((l) => [...l, `HTTP ${resp.status}`]);
            setStatus("error");
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

                // Detect error patterns in the output
                if (
                    line.includes("[error]") ||
                    line.includes("fatal:") ||
                    line.includes("Error:") ||
                    line.includes("Failed") ||
                    line.match(/command exited with \d+:/)
                ) {
                    hasError = true;
                }

                try {
                    const obj = JSON.parse(line);
                    if (obj?.line) setLogs((l) => [...l, obj.line]);
                    else setLogs((l) => [...l, line]);
                } catch {
                    setLogs((l) => [...l, line]);
                }
            }
        }
        // Set status based on whether errors were detected in the logs
        setStatus(hasError ? "error" : "success");
    } catch (e: any) {
        setLogs((l) => [...l, `Error: ${e?.message || e}`]);
        setStatus("error");
    } finally {
        setRunning(false);
    }
}

function Box({ title, icon, children, status, variant = "default" }: { title: string; icon: string; children: React.ReactNode; status?: Status; variant?: "default" | "primary" }) {
    const variantClasses = variant === "primary"
        ? "border-drupal-300 dark:border-drupal-700 bg-gradient-to-br from-white to-drupal-50 dark:from-gray-800 dark:to-drupal-950"
        : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800";

    return (
        <section className={`border rounded-2xl p-6 mb-6 shadow-lg hover:shadow-xl transition-all duration-300 animate-slide-up ${variantClasses}`} aria-labelledby={`section-${title.replace(/\s+/g, '-').toLowerCase()}`}>
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                    <span className="text-3xl" role="img" aria-hidden="true">{icon}</span>
                    <h2 id={`section-${title.replace(/\s+/g, '-').toLowerCase()}`} className="text-2xl font-bold text-gray-900 dark:text-gray-100">{title}</h2>
                </div>
                {status && <StatusBadge status={status} />}
            </div>
            {children}
        </section>
    );
}

function LogPane({ logs, collapsed, onToggle }: { logs: string[]; collapsed: boolean; onToggle: () => void }) {
    const logsText = logs.join("\n");

    return (
        <div className="mt-5" role="region" aria-label="Log output">
            <div className="flex items-center justify-between mb-3">
                <button
                    onClick={onToggle}
                    className="text-sm font-medium text-drupal-600 dark:text-drupal-400 hover:text-drupal-700 dark:hover:text-drupal-300 transition-colors flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-drupal-500 rounded px-2 py-1"
                    aria-expanded={!collapsed}
                    aria-label={`${collapsed ? "Show" : "Hide"} log output with ${logs.length} lines`}
                >
                    <span className="text-lg" aria-hidden="true">{collapsed ? "▶" : "▼"}</span>
                    <span>{collapsed ? "Show" : "Hide"} logs ({logs.length} lines)</span>
                </button>
                {!collapsed && logs.length > 0 && <CopyButton text={logsText} />}
            </div>
            {!collapsed && (
                <pre className="font-mono text-xs bg-gradient-to-br from-gray-900 to-gray-950 dark:from-black dark:to-gray-900 text-blue-100 dark:text-blue-200 p-5 rounded-xl max-h-96 overflow-auto whitespace-pre-wrap shadow-inner border border-gray-700 animate-fade-in" role="log" aria-live="polite" aria-atomic="false">
                    {logs.length === 0 ? (
                        <div className="text-gray-500 italic">No logs yet...</div>
                    ) : (
                        logs.map((l, i) => (
                            <div key={i} className="hover:bg-white/5 px-1 rounded">
                                {l}
                            </div>
                        ))
                    )}
                </pre>
            )}
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
        <div className="my-5">
            <div className="font-bold mb-2 text-lg text-gray-900 dark:text-gray-100">{title}</div>
            <div className="text-gray-800 dark:text-gray-200 leading-relaxed">{children}</div>
        </div>
    );

    const List = ({ items }: { items: string[] }) => (
        <ul className="mt-3 ml-6 space-y-2 list-disc text-gray-800 dark:text-gray-200">
            {items?.map((x, i) => (
                <li key={i}>{x}</li>
            ))}
        </ul>
    );

    return (
        <Box title="Plan Preview" icon="🧭">
            <div className="flex gap-3 items-center mb-5 flex-wrap">
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-123)"
                    className="flex-1 min-w-[240px] px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-drupal-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 transition-all"
                />
                <button
                    disabled={!issueKey || loading}
                    onClick={act}
                    className="px-6 py-3 bg-gradient-to-r from-drupal-500 to-drupal-600 hover:from-drupal-600 hover:to-drupal-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl"
                >
                    {loading ? "⏳ Generating…" : "✨ Generate Plan"}
                </button>
            </div>

            {error && (
                <div className="p-4 bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 rounded-xl animate-fade-in">
                    ❌ {error}
                </div>
            )}

            {data && (
                <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 border-2 border-gray-200 dark:border-gray-700 rounded-xl p-5 animate-fade-in">
                    <div className="text-sm space-y-3">
                        <div className="flex items-center gap-2">
                            <strong className="text-gray-900 dark:text-gray-100">Issue:</strong>
                            <span className="text-gray-700 dark:text-gray-300 font-mono">{data.issue_key}</span>
                        </div>
                        <div>
                            <strong className="text-gray-900 dark:text-gray-100">Summary:</strong>
                            <span className="text-gray-700 dark:text-gray-300 ml-2">{data.summary || "(no title)"}</span>
                        </div>
                        <div>
                            <strong className="text-gray-900 dark:text-gray-100">Suggested module:</strong>
                            <code className="ml-2 px-2.5 py-1 bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded font-mono text-sm">{data.suggested_module_name}</code>
                        </div>
                    </div>
                    {data.description_md && (
                        <Section title="Description">
                            <pre className="whitespace-pre-wrap bg-white dark:bg-gray-800 p-4 rounded-lg text-sm shadow-inner">{data.description_md}</pre>
                            {data.description_checklist?.length ? <List items={data.description_checklist} /> : null}
                        </Section>
                    )}
                    {data.acceptance_md && (
                        <Section title="Acceptance Criteria">
                            <pre className="whitespace-pre-wrap bg-white dark:bg-gray-800 p-4 rounded-lg text-sm shadow-inner">{data.acceptance_md}</pre>
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
    const [status, setStatus] = React.useState<Status>("idle");
    const [collapsed, setCollapsed] = React.useState(true);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        setCollapsed(false);
        const qs = new URLSearchParams({ issue_key: issueKey.trim() });
        await streamGET(`${apiBase}/stream/one-shot?${qs.toString()}`, setLogs, setRunning, setStatus);
    };

    return (
        <Box title="One-Shot Workflow" icon="🚀" status={status} variant="primary">
            <p className="text-gray-700 dark:text-gray-300 mb-4 text-sm">
                Complete automation: Jira → MR → Review/Merge → Deploy → QA
            </p>
            <div className="flex gap-3 items-center flex-wrap">
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-123)"
                    className="flex-1 min-w-[240px] px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-drupal-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 transition-all"
                />
                <button
                    disabled={!issueKey || running}
                    onClick={act}
                    className="px-8 py-3 bg-gradient-to-r from-drupal-500 to-drupal-600 hover:from-drupal-600 hover:to-drupal-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl text-lg"
                >
                    {running ? "🔄 Running…" : "▶️ Run One-Shot"}
                </button>
            </div>
            <LogPane logs={logs} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </Box>
    );
}

/** STEP 1: Open MR (copilot-workflow) */
function Step1WorkflowTile() {
    const [issueKey, setIssueKey] = React.useState("");
    const [running, setRunning] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);
    const [status, setStatus] = React.useState<Status>("idle");
    const [collapsed, setCollapsed] = React.useState(true);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        setCollapsed(false);
        const qs = new URLSearchParams({ issue_key: issueKey.trim() });
        await streamGET(`${apiBase}/stream/workflow-cli?${qs.toString()}`, setLogs, setRunning, setStatus);
    };

    return (
        <Box title="Step 1: Open MR" icon="📝" status={status}>
            <p className="text-gray-700 dark:text-gray-300 mb-4 text-sm">
                Create branch, generate code, and open merge request
            </p>
            <div className="flex gap-3 items-center flex-wrap">
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-104)"
                    className="flex-1 min-w-[240px] px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-drupal-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 transition-all"
                />
                <button
                    disabled={!issueKey || running}
                    onClick={act}
                    className="px-6 py-3 bg-gradient-to-r from-drupal-500 to-drupal-600 hover:from-drupal-600 hover:to-drupal-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl"
                >
                    {running ? "🔄 Running…" : "▶️ Run Workflow"}
                </button>
            </div>
            <LogPane logs={logs} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
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
    const [status, setStatus] = React.useState<Status>("idle");
    const [collapsed, setCollapsed] = React.useState(true);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        setCollapsed(false);
        const qs = new URLSearchParams({
            mr_url: mrUrl.trim(),
            auto_merge: String(autoMerge),
            deploy: String(deploy),
            verbose: String(verbose),
        });
        await streamGET(`${apiBase}/stream/ai-review-merge-cli?${qs.toString()}`, setLogs, setRunning, setStatus);
    };

    return (
        <Box title="Step 2: Review & Deploy" icon="✅" status={status}>
            <p className="text-gray-700 dark:text-gray-300 mb-4 text-sm">
                AI review, merge to staging, and trigger deployment
            </p>
            <div className="flex gap-3 items-center flex-wrap mb-4">
                <input
                    value={mrUrl}
                    onChange={(e) => setMrUrl(e.target.value)}
                    placeholder="MR URL"
                    className="flex-1 min-w-[320px] px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-drupal-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 transition-all"
                />
                <button
                    disabled={!mrUrl || running}
                    onClick={act}
                    className="px-6 py-3 bg-gradient-to-r from-drupal-500 to-drupal-600 hover:from-drupal-600 hover:to-drupal-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl"
                >
                    {running ? "🔄 Running…" : "▶️ Review & Merge"}
                </button>
            </div>
            <div className="flex gap-5 flex-wrap bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
                <label className="flex items-center gap-2.5 cursor-pointer group">
                    <input
                        type="checkbox"
                        checked={autoMerge}
                        onChange={(e) => setAutoMerge(e.target.checked)}
                        className="w-5 h-5 text-drupal-500 rounded focus:ring-2 focus:ring-drupal-500 cursor-pointer"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-drupal-600 dark:group-hover:text-drupal-400">--auto-merge</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer group">
                    <input
                        type="checkbox"
                        checked={deploy}
                        onChange={(e) => setDeploy(e.target.checked)}
                        className="w-5 h-5 text-drupal-500 rounded focus:ring-2 focus:ring-drupal-500 cursor-pointer"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-drupal-600 dark:group-hover:text-drupal-400">--deploy</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer group">
                    <input
                        type="checkbox"
                        checked={verbose}
                        onChange={(e) => setVerbose(e.target.checked)}
                        className="w-5 h-5 text-drupal-500 rounded focus:ring-2 focus:ring-drupal-500 cursor-pointer"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-drupal-600 dark:group-hover:text-drupal-400">--verbose</span>
                </label>
            </div>
            <LogPane logs={logs} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </Box>
    );
}

/** STEP 3: QA on EC2 (copilot-qa-ec2) */
function Step3QATile() {
    const [issueKey, setIssueKey] = React.useState("");
    const [running, setRunning] = React.useState(false);
    const [logs, setLogs] = React.useState<string[]>([]);
    const [status, setStatus] = React.useState<Status>("idle");
    const [collapsed, setCollapsed] = React.useState(true);

    const act = async () => {
        setRunning(true);
        setLogs([]);
        setCollapsed(false);
        const qs = new URLSearchParams({ issue_key: issueKey.trim() });
        await streamGET(`${apiBase}/stream/qa-ec2-cli?${qs.toString()}`, setLogs, setRunning, setStatus);
    };

    return (
        <Box title="Step 3: QA Verification" icon="🧪" status={status}>
            <p className="text-gray-700 dark:text-gray-300 mb-4 text-sm">
                Run Drush QA checks on EC2 and update Jira status
            </p>
            <div className="flex gap-3 items-center flex-wrap">
                <input
                    value={issueKey}
                    onChange={(e) => setIssueKey(e.target.value)}
                    placeholder="Jira key (e.g., CCS-104)"
                    className="flex-1 min-w-[240px] px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-drupal-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 transition-all"
                />
                <button
                    disabled={!issueKey || running}
                    onClick={act}
                    className="px-6 py-3 bg-gradient-to-r from-drupal-500 to-drupal-600 hover:from-drupal-600 hover:to-drupal-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl"
                >
                    {running ? "🔄 Running…" : "▶️ Run QA"}
                </button>
            </div>
            <LogPane logs={logs} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </Box>
    );
}

export default function Home() {
    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                <Header />

                <main role="main">
                    {/* One-click */}
                    <OneShotCLITile />

                    {/* Step-by-step */}
                    <nav aria-label="Workflow steps" className="space-y-6">
                        <Step1WorkflowTile />
                        <Step2ReviewMergeDeployTile />
                        <Step3QATile />
                    </nav>

                    {/* Optional helper */}
                    <aside className="mt-8" aria-label="Additional tools">
                        <PlanPreviewBox />
                    </aside>
                </main>

                {/* Footer */}
                <footer className="mt-12 text-center text-sm text-gray-600 dark:text-gray-400" role="contentinfo">
                    <p>Powered by Drupal, FastAPI, and Ollama</p>
                </footer>
            </div>
        </div>
    );
}
