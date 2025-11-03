"use client";

import React from "react";

type PaletteProps = {
    onAddClick?: (type: string) => void; // optional: click-to-add
};

const ITEMS = [
    { type: "jiraTrigger", label: "Jira Trigger" },
    { type: "createMr",    label: "Create MR" },
    { type: "planPatch",   label: "Plan & Patch" },
    { type: "ciWait",      label: "CI Wait" },
    { type: "deploy",      label: "Deploy" },
    { type: "qa",          label: "QA" },
];

export function Palette({ onAddClick }: PaletteProps) {
    const onDragStart = (e: React.DragEvent<HTMLButtonElement>, type: string) => {
        // React Flow checks these keys; we set all three to be safe across versions
        e.dataTransfer.setData("application/reactflow", type);
        e.dataTransfer.setData("application/reactflow-node", type);
        e.dataTransfer.setData("application/reactflow/type", type);
        e.dataTransfer.effectAllowed = "move";
    };

    return (
        <div>
            <p className="text-sm text-muted-foreground mb-2">
                Drag or click to add nodes.
            </p>
            <div className="space-y-2">
                {ITEMS.map((it) => (
                    <button
                        key={it.type}
                        className="w-full rounded border px-3 py-2 text-left hover:bg-accent"
                        draggable
                        onDragStart={(e) => onDragStart(e, it.type)}
                        onClick={() => onAddClick?.(it.type)}
                    >
                        {it.label}
                    </button>
                ))}
            </div>
        </div>
    );
}
