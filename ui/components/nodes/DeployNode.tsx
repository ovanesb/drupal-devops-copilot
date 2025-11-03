"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
export default function PlanPatchNode({ data }: NodeProps) {
    return (
        <div className="rounded-2xl border bg-card shadow p-3 w-[220px]">
            <h3 className="font-medium">Deploy</h3>
            <p className="text-xs text-muted-foreground mt-1">Generate plan / apply patch.</p>
            <Handle type="target" position={Position.Left} />
            <Handle type="source" position={Position.Right} />
        </div>
    );
}
