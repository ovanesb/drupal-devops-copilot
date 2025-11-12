// ui/components/RunPanel.tsx
import { useState } from "react";
import type { Node, Edge } from "@xyflow/react";
import { Button } from "@/components/ui/button";

export default function RunPanel({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
    const [jobId, setJobId] = useState<string | null>(null);
    const [lines, setLines] = useState<string[]>([]);
    const [running, setRunning] = useState(false);

    async function start() {
        setRunning(true);
        setLines([]);

        const workflow = {
            version: "v1",
            nodes: nodes.map(n => ({ id: n.id, type: n.type as string, data: n.data })),
            edges: edges.map(e => ({ source: e.source, target: e.target })),
        };

        const r = await fetch("/api/run", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ workflow, dry_run: false }),
        }).then(r => r.json());

        setJobId(r.job_id);

        const es = new EventSource(`/api/stream/${r.job_id}`);
        es.addEventListener("step", (e: MessageEvent) => {
            const d = JSON.parse(e.data);
            setLines(prev => prev.concat(`\n▶ ${d.label}: ${d.cmd}`));
        });
        es.addEventListener("log", (e: MessageEvent) => {
            const d = JSON.parse(e.data);
            setLines(prev => prev.concat(d.line));
        });
        es.addEventListener("done", (e: MessageEvent) => {
            const d = JSON.parse(e.data);
            setLines(prev => prev.concat(`\n— ${d.label} exited ${d.rc}`));
        });
        es.addEventListener("error", (e: MessageEvent) => {
            const msg = safeJSON((e as any).data)?.msg ?? "unknown";
            setLines(prev => prev.concat(`\n✖ error: ${msg}`));
            es.close(); setRunning(false);
        });
        es.addEventListener("complete", () => {
            setLines(prev => prev.concat("\n✓ complete"));
            es.close(); setRunning(false);
        });

        function safeJSON(x: any) { try { return JSON.parse(x); } catch { return null; } }
    }

    return (
        <div className="h-full flex flex-col">
            <div className="p-2 border-b flex items-center gap-2">
                <Button onClick={start} disabled={running}>Run</Button>
                {jobId && <span className="text-xs text-muted-foreground">job: {jobId}</span>}
            </div>
            <pre className="flex-1 m-0 p-3 bg-black text-white text-xs overflow-auto whitespace-pre-wrap">
        {lines.join("")}
      </pre>
        </div>
    );
}
