"use client";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { v4 as uuid } from "uuid";
import { useFlowStore } from "@/lib/store";

const NODE_PRESETS = [
    { type: "jiraTrigger", label: "Jira Trigger" },
    { type: "planPatch", label: "Plan & Patch" },
    { type: "createMR", label: "Create MR" },
    { type: "ciWait", label: "CI Wait" },
    { type: "deploy", label: "Deploy" },
    { type: "qa", label: "QA" },
] as const;

export function Palette() {
    const addNode = useFlowStore((s) => s.addNode);
    const initialPosition = useMemo(() => ({ x: 250, y: 100 }), []);

    return (
        <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Drag or click to add nodes.</p>
            <Separator />
            <div className="grid grid-cols-2 gap-2">
                {NODE_PRESETS.map((p) => (
                    <Button
                        key={p.type}
                        variant="outline"
                        onClick={() =>
                            addNode({
                                id: uuid(),
                                type: p.type as any,
                                position: initialPosition,
                                data: { title: p.label },
                            })
                        }
                    >
                        {p.label}
                    </Button>
                ))}
            </div>
        </div>
    );
}
