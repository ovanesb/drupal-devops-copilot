"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { IntegrationProfileDrawer } from "@/components/IntegrationProfileDrawer";

export default function JiraTriggerNode({ data }: NodeProps) {
    const [open, setOpen] = useState(false);

    const title =
        typeof (data as any)?.title === "string"
            ? (data as any).title
            : "Jira Trigger";

    return (
        <div className="rounded-2xl border bg-card text-card-foreground shadow p-3 w-[240px]">
            <div className="flex items-center justify-between">
                <h3 className="font-medium">{title}</h3>
            </div>

            <p className="text-xs text-muted-foreground mt-1">
                Starts workflow from Jira key/label.
            </p>

            {/* Profile UI disabled for now until store exposes profiles & attach function */}
            <div className="mt-2 space-y-2">
                <div className="text-xs">
                    <span className="font-semibold">Profile:</span> None
                </div>
                <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
                        Create profile
                    </Button>
                    <select
                        className="flex-1 rounded-md border bg-background px-2 py-1 text-sm"
                        disabled
                        value=""
                        onChange={() => {}}
                    >
                        <option>Pick profile…</option>
                    </select>
                </div>
            </div>

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
