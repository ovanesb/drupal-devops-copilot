"use client";

import React, { useCallback, useMemo } from "react";
import {
    ReactFlow,
    ReactFlowProvider,
    Background,
    Controls,
    MiniMap,
    addEdge,
    applyNodeChanges,
    applyEdgeChanges,
    useNodesState,
    useEdgesState,
    useReactFlow,
    type Connection,
    type Edge,
    type EdgeChange,
    type Node,
    type NodeChange,
    type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Palette } from "@/components/Palette";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useFlowStore } from "@/lib/store";
import { nodeTypesMap } from "@/components/nodes";
import { validateWorkflow } from "@/lib/validation";
import { useWorkflow } from "@/hooks/useWorkflow";
import InspectorPanel from "@/components/InspectorPanel";
import RunPanel from "@/components/RunPanel";

// ---- small error boundary so the app doesn’t white-screen ----
class Boundary extends React.Component<{ children: React.ReactNode }, { err?: any }> {
    state = { err: undefined as any };
    static getDerivedStateFromError(err: any) {
        return { err };
    }
    componentDidCatch(err: any, info: any) {
        console.error("[FlowBuilder crash]", err, info);
    }
    render() {
        if (this.state.err) {
            return (
                <div className="p-4 text-sm text-red-600">
                    Oops, something went wrong in the canvas. Check console for details.
                    <div className="mt-2">
                        <Button variant="outline" onClick={() => this.setState({ err: undefined })}>
                            Try again
                        </Button>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

// Ensure nodes always have fields our custom nodes expect.
const withDefaults = <T extends { data?: any; type?: string }>(n: T) => {
    const d = n.data ?? {};
    return {
        ...n,
        data: {
            ...d,
            // fill only if missing
            label: (d as any).label ?? n.type ?? "Node",
            profileId: (d as any).profileId ?? null,
            config: { ...(d as any).config ?? {} },
        },
    };
};

function FlowInner() {
    const {
        nodes,
        edges,
        setNodes: setStoreNodes,
        setEdges: setStoreEdges,
        reset,
        selectNode,
    } = useFlowStore();

    // React Flow local state (bootstrapped once from store)
    const [rfNodes, setRfNodes, rfOnNodesChange] = useNodesState(nodes.map(withDefaults));
    const [rfEdges, setRfEdges, rfOnEdgesChange] = useEdgesState(edges);
    const [selectedId, setSelectedId] = React.useState<string | null>(null);

    // derive the live selected node from rfNodes by our local id
    const selectedNode: Node | null = useMemo(
        () => (selectedId ? rfNodes.find((n) => n.id === selectedId) ?? null : null),
        [rfNodes, selectedId]
    );

    // Mirror RF changes to store using apply* helpers
    const onNodesChange = useCallback(
        (changes: NodeChange[]) => {
            setRfNodes((prev) => {
                const next = applyNodeChanges(changes, prev);
                setStoreNodes(next);
                return next;
            });
            rfOnNodesChange(changes);
        },
        [setRfNodes, setStoreNodes, rfOnNodesChange]
    );

    const onEdgesChange = useCallback(
        (changes: EdgeChange[]) => {
            setRfEdges((prev) => {
                const next = applyEdgeChanges(changes, prev);
                setStoreEdges(next);
                return next;
            });
            rfOnEdgesChange(changes);
        },
        [setRfEdges, setStoreEdges, rfOnEdgesChange]
    );

    const onConnect = useCallback(
        (params: Edge | Connection) => {
            setRfEdges((eds) => {
                const next = addEdge({ ...params, animated: true }, eds);
                setStoreEdges(next);
                return next;
            });
        },
        [setRfEdges, setStoreEdges]
    );

    const nodeTypes: NodeTypes = useMemo(() => nodeTypesMap, []);

    // ===== API wiring (workflow id = 1 for now) =====
    const { workflowQuery, saveWorkflow } = useWorkflow(1);

    const onSave = () => {
        try {
            const payload = {
                name: "demo",
                nodes: rfNodes.map((n) => ({
                    id: n.id,
                    type: String(n.type),
                    position: n.position,
                    data: n.data ?? {}, // include edited data
                })),
                edges: rfEdges.map((e) => ({
                    id: e.id ?? `${e.source}-${e.target}`,
                    source: e.source!,
                    target: e.target!,
                })),
            };

            // optional schema check
            // validateWorkflow.parse(payload);

            saveWorkflow.mutate(payload as any, {
                onSuccess: () => alert("Saved ✨"),
                onError: (e: any) => alert("Save failed: " + (e?.message ?? "unknown")),
            });
        } catch (e: any) {
            alert("Validation failed: " + (e?.message ?? "unknown"));
        }
    };

    const onLoad = () => {
        const data = workflowQuery.data as | { nodes?: Node[]; edges?: Edge[] } | undefined;
        if (data) {
            const nextNodes = (data.nodes || []).map(withDefaults);
            const nextEdges = data.edges || [];
            setRfNodes(nextNodes);
            setRfEdges(nextEdges);
            setStoreNodes(nextNodes);
            setStoreEdges(nextEdges);
        } else {
            alert("No saved workflow yet");
        }
    };

    // Delete selected
    const onDeleteSelected = () => {
        setRfNodes((ns) => {
            const next = ns.filter((n) => !n.selected);
            setStoreNodes(next);
            return next;
        });
        setRfEdges((es) => {
            const next = es.filter((e) => !e.selected);
            setStoreEdges(next);
            return next;
        });
    };

    const deleteKeys = ["Backspace", "Delete"] as const;
    const onKeyDown = (e: React.KeyboardEvent) => {
        if (deleteKeys.includes(e.key as (typeof deleteKeys)[number])) {
            e.preventDefault();
            onDeleteSelected();
        }
    };

    // selection guard (still informs store, but Inspector derives from local id)
    const safeSelect = (_: any, n: any) => {
        try {
            if (n?.id) {
                console.log("[safeSelect] id=", n.id);       // <-- add this
                setSelectedId(n.id);
                if (typeof selectNode === "function") selectNode(n.id);
            }
        } catch (err) {
            console.error("[selectNode error]", err);
        }
    };

    // ---- Drag & Drop (v12) ----
    const rf = useReactFlow();

    const onDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
    }, []);

    const onDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            const type =
                e.dataTransfer.getData("application/reactflow") ||
                e.dataTransfer.getData("application/reactflow-node") ||
                e.dataTransfer.getData("application/reactflow/type");
            if (!type) return;

            const pane = (e.target as HTMLElement).closest(".react-flow__pane") as HTMLElement | null;
            const bounds = pane?.getBoundingClientRect();
            const pos = rf.screenToFlowPosition({
                x: e.clientX - (bounds?.left ?? 0),
                y: e.clientY - (bounds?.top ?? 0),
            });

            const newNode: Node = {
                id: crypto.randomUUID(),
                type,
                position: pos,
                data: { label: type }, // Inspector adds type-specific fields
            };

            setRfNodes((ns) => {
                const next = ns.concat(withDefaults(newNode));
                setStoreNodes(next);
                return next;
            });
        },
        [rf, setRfNodes, setStoreNodes]
    );

    // Commit from Inspector → write into RF nodes and store
    const onCommitFromInspector = (next: { id: string; data: any; type?: string; position?: any }) => {
        setRfNodes((prev) => {
            const updated = prev.map((n) =>
                n.id === next.id
                    ? {
                        ...n,
                        type: (next as any).type ?? n.type,
                        position: (next as any).position ?? n.position,
                        data: { ...(n.data ?? {}), ...(next.data ?? {}) },
                    }
                    : n
            );
            console.log("[onCommitFromInspector] merged node=", updated.find(u => u.id === next.id));

            setStoreNodes(updated);
            return updated;
        });
    };

    return (
        <div className="h-full grid grid-cols-[320px_1fr_320px]" onKeyDown={onKeyDown} tabIndex={0}>
            {/* LEFT: palette/actions */}
            <aside className="border-r bg-card p-3 overflow-y-auto">
                <div className="flex items-center justify-between">
                    <h1 className="text-lg font-semibold">Flow Builder</h1>
                </div>
                <Separator className="my-3" />
                <Palette />
                <Separator className="my-3" />
                <div className="flex gap-2">
                    <Button variant="secondary" onClick={() => reset()}>
                        Reset
                    </Button>
                    <Button variant="outline" onClick={onDeleteSelected}>
                        Delete selected
                    </Button>
                </div>
                <div className="mt-2 flex gap-2">
                    <Button onClick={onSave} variant="outline">
                        Save
                    </Button>
                    <Button onClick={onLoad} variant="outline">
                        Load
                    </Button>
                </div>
            </aside>

            {/* MIDDLE: canvas */}
            <div className="h-full">
                <Boundary>
                    <ReactFlow
                        nodes={rfNodes}
                        edges={rfEdges}
                        nodeTypes={nodeTypes}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        onNodeClick={safeSelect}
                        onDrop={onDrop}
                        onDragOver={onDragOver}
                        fitView
                        deleteKeyCode={deleteKeys as any}
                        snapToGrid
                        snapGrid={[10, 10]}
                    >
                        <MiniMap />
                        <Controls />
                        <Background gap={16} />
                    </ReactFlow>
                </Boundary>
            </div>

            {/* RIGHT: Inspector + Run */}
            <aside className="border-l bg-background/50 overflow-y-auto">
                <div className="grid grid-rows-[auto_auto_minmax(0,1fr)] h-full">
                    <div className="p-2 font-medium border-b">Inspector</div>
                    <div className="p-2">
                        <InspectorPanel selectedNode={selectedNode as any} onCommit={onCommitFromInspector} />
                    </div>
                    <div className="p-2 font-medium border-t">Run</div>
                    <div className="min-h-0">
                        <RunPanel nodes={rfNodes} edges={rfEdges} />
                    </div>
                </div>
            </aside>
        </div>
    );
}

export default function FlowBuilder() {
    return (
        <ReactFlowProvider>
            <FlowInner />
        </ReactFlowProvider>
    );
}
