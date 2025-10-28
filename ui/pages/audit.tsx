// ui/pages/audit.tsx
import * as React from "react";
import Header from "../components/Header";
import StatusBadge from "../components/StatusBadge";
import CopyButton from "../components/CopyButton";

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
        <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                <Header />

                <main role="main">
                    <section className="border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 rounded-2xl p-6 mb-6 shadow-lg hover:shadow-xl transition-all duration-300 animate-slide-up">
                        <div className="flex items-center justify-between mb-5">
                            <div className="flex items-center gap-3">
                                <span className="text-3xl" role="img" aria-hidden="true">📋</span>
                                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Audit Trail</h1>
                            </div>
                        </div>
                        <div className="flex gap-3 items-center mb-5 flex-wrap">
                            <input
                                value={limit}
                                onChange={(e) => setLimit(parseInt(e.target.value || "200", 10))}
                                type="number"
                                min={10}
                                max={1000}
                                className="w-32 px-4 py-2 border-2 border-gray-300 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-drupal-500 focus:border-transparent dark:bg-gray-700 dark:text-gray-100 transition-all"
                                aria-label="Event limit"
                            />
                            <button
                                onClick={loadList}
                                disabled={loading}
                                className="px-6 py-2 bg-gradient-to-r from-drupal-500 to-drupal-600 hover:from-drupal-600 hover:to-drupal-700 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg hover:shadow-xl"
                            >
                                {loading ? "🔄 Loading…" : "🔄 Refresh"}
                            </button>
                        </div>

                        <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full border-collapse text-sm">
                                    <thead className="bg-gray-100 dark:bg-gray-900">
                                        <tr>
                                            <th className="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Time (UTC)</th>
                                            <th className="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Run</th>
                                            <th className="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Action</th>
                                            <th className="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Status</th>
                                            <th className="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Message</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                        {events.map((e, i) => (
                                            <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                                <td className="px-4 py-3 whitespace-nowrap text-gray-600 dark:text-gray-400 font-mono text-xs">{e.ts}</td>
                                                <td className="px-4 py-3">
                                                    <button
                                                        onClick={() => loadRun(e.run_id)}
                                                        className="text-drupal-600 dark:text-drupal-400 hover:text-drupal-700 dark:hover:text-drupal-300 font-mono text-xs underline hover:no-underline transition-colors"
                                                    >
                                                        {e.run_id}
                                                    </button>
                                                </td>
                                                <td className="px-4 py-3 text-gray-700 dark:text-gray-300 font-medium">{e.action}</td>
                                                <td className="px-4 py-3">
                                                    <StatusBadge status={e.status === "success" ? "success" : e.status === "error" ? "error" : e.status === "running" ? "running" : "idle"} />
                                                </td>
                                                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{e.message}</td>
                                            </tr>
                                        ))}
                                        {!events.length && (
                                            <tr>
                                                <td colSpan={5} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400 italic">
                                                    No events yet.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </section>

                    {selected && (
                        <section className="border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-lg hover:shadow-xl transition-all duration-300 animate-fade-in">
                            <div className="flex items-center justify-between mb-5">
                                <div className="flex items-center gap-3">
                                    <span className="text-3xl" role="img" aria-hidden="true">🔍</span>
                                    <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Run Details</h2>
                                </div>
                                <CopyButton text={JSON.stringify(selected, null, 2)} />
                            </div>
                            <pre className="font-mono text-xs bg-gradient-to-br from-gray-900 to-gray-950 dark:from-black dark:to-gray-900 text-blue-100 dark:text-blue-200 p-5 rounded-xl max-h-96 overflow-auto whitespace-pre-wrap shadow-inner border border-gray-700">
                                {JSON.stringify(selected, null, 2)}
                            </pre>
                        </section>
                    )}
                </main>

                <footer className="mt-12 text-center text-sm text-gray-600 dark:text-gray-400" role="contentinfo">
                    <p>Powered by Drupal, FastAPI, and Ollama</p>
                </footer>
            </div>
        </div>
    );
}
