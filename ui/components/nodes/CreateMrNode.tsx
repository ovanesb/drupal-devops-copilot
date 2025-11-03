"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

type CreateMrData = {
    title?: string;
    target?: string;
    profileId?: string | null;
};

export default function CreateMrNode({ data }: NodeProps) {
    // Safely narrow the unknown `data` to our shape
    const d = (data ?? {}) as Partial<CreateMrData>;

    const title = d.title ?? "Create MR";
    const target = d.target ?? "default";

    return (
        <div className="rounded-2xl border bg-card text-card-foreground shadow p-3 w-[220px]">
            <h3 className="font-medium">{title}</h3>
            <p className="text-xs text-muted-foreground mt-1">Target: {target}</p>

            <Handle type="target" position={Position.Left} />
            <Handle type="source" position={Position.Right} />
        </div>
    );
}
