"use client";

import React, { useCallback, useMemo, useState, useEffect } from "react";
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
import InspectorPanel from "@/components/InspectorPanel"; // ✅ mount the Inspector

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

// Ensure nodes always have fields our custom nodes expect
const withDefaults = <T extends { data?: any }>(n: T) => ({
    ...n,
    data: {
        label: n?.data?.label ?? "Node",
        profileId: n?.data?.profileId ?? null,
        // NOTE: keep config bucket but allow flat fields too (Inspector reads/writes flat)
        config: n?.data?.config ?? {},
        ...n?.data,
    },
});

function FlowInner() {
    const {
        nodes,
        edges,
        // rename store setters so we never confuse them with RF setters
        setNodes: setStoreNodes,
        setEdges: setStoreEdges,
        reset,
        selectNode,
    } = useFlowStore();

    // React Flow local state (bootstrapped once from store)
    const [rfNodes, setRfNodes, rfOnNodesChange] = useNodesState(nodes.map(withDefaults));
    const [rfEdges, setRfEdges, rfOnEdgesChange] = useEdgesState(edges);

    // Currently selected node (derived from RF selection)
    const selectedNode: Node | null = useMemo(
        () => rfNodes.find((n) => n.selected) ?? null,
        [rfNodes]
    );

    // Mirror RF changes to store using apply* helpers
    const onNodesChange = useCallback(
        (changes: NodeChange[]) => {
            setRfNodes((prev) => {
                const next = applyNodeChanges(changes, prev);
                setStoreNodes(next); // store always receives arrays (not functions)
                return next;
            });
            rfOnNodesChange(changes); // keep RF internals happy
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
            validateWorkflow.parse({ nodes: rfNodes, edges: rfEdges });
            saveWorkflow.mutate(
                { name: "demo", nodes: rfNodes.map(withDefaults), edges: rfEdges },
                {
                    onSuccess: () => alert("Saved ✨"),
                    onError: (e: any) => alert("Save failed: " + (e?.message ?? "unknown")),
                }
            );
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

    // selection guard (still informs store, but Inspector derives from RF)
    const safeSelect = (_: any, n: any) => {
        try {
            if (n?.id && typeof selectNode === "function") selectNode(n.id);
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
                data: { label: type }, // Inspector will add type-specific fields
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
    const onCommitFromInspector = useCallback(
        (updated: any) => {
            setRfNodes((prev) => {
                const next = prev.map((n) => {
                    if (n.id !== updated.id) return n;

                    // Merge data and ensure the label lives under data.label
                    const mergedData = {
                        ...n.data,
                        ...updated.data,
                        label: updated.label ?? (n.data as any)?.label ?? "",
                        config: {
                            ...(n.data as any)?.config ?? {},
                            ...(updated.data?.config ?? {}),
                        },
                    };

                    return {
                        ...n,
                        data: mergedData, // <-- no top-level `label` on Node
                    };
                });
                setStoreNodes(next);
                return next;
            });
        },
        [setRfNodes, setStoreNodes]
    );


    return (
        // ⬅️ Palette | Canvas | Inspector ➡️
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

            {/* RIGHT: Inspector */}
            <aside className="border-l bg-background/50 overflow-y-auto">
                <InspectorPanel selectedNode={selectedNode as any} onCommit={onCommitFromInspector} />
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
