"use client";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { IntegrationProfileDrawer } from "@/components/IntegrationProfileDrawer";
import { useFlowStore } from "@/lib/store";

export default function JiraTriggerNode({ data, id }: NodeProps) {
    const [open, setOpen] = useState(false);
    const { profiles, attachProfileToNode } = useFlowStore();
    const nodeProfile = profiles.find((p) => p.id === data?.profileId);

    return (
        <div className="rounded-2xl border bg-card text-card-foreground shadow p-3 w-[240px]">
            <div className="flex items-center justify-between">
                <h3 className="font-medium">{data?.title ?? "Jira Trigger"}</h3>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
                Starts workflow from Jira key/label.
            </p>
            <div className="mt-2 space-y-2">
                <div className="text-xs">
                    <span className="font-semibold">Profile:</span>{" "}
                    {nodeProfile ? nodeProfile.name : "None"}
                </div>
                <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
                        Create profile
                    </Button>
                    <select
                        className="flex-1 rounded-md border bg-background px-2 py-1 text-sm"
                        value={data?.profileId ?? ""}
                        onChange={(e) => attachProfileToNode(id, e.target.value)}
                    >
                        <option value="">Pick profile…</option>
                        {profiles
                            .filter((p) => p.kind === "jira")
                            .map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.name}
                                </option>
                            ))}
                    </select>
                </div>
            </div>

            {/* Allow both incoming and outgoing edges */}
            <Handle type="target" position={Position.Left} />
            <Handle type="source" position={Position.Right} />

            <IntegrationProfileDrawer
                open={open}
                onOpenChange={setOpen}
                defaultKind="jira"
            />
        </div>
    );
}
