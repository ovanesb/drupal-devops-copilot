"use client";
import React, { useCallback, useMemo } from "react";
import {
    ReactFlow,
    Background,
    Controls,
    addEdge,
    MiniMap,
    Connection,
    Edge,
    useNodesState,
    useEdgesState,
    NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Palette } from "@/components/Palette";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useFlowStore } from "@/lib/store";
import { nodeTypesMap } from "@/components/nodes";
import { validateWorkflow } from "@/lib/validation";
import { useWorkflow } from "@/hooks/useWorkflow";

export function FlowBuilder() {
    const { nodes, edges, setNodes, setEdges, reset, selectNode } = useFlowStore();

    // Initialize RF state from current store values
    const [rfNodes, setRfNodes, onNodesChange] = useNodesState(nodes);
    const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState(edges);

    // ---- SYNC: store -> RF (so palette/add/load shows up immediately) ----
    React.useEffect(() => {
        setRfNodes(nodes);
    }, [nodes, setRfNodes]);

    React.useEffect(() => {
        setRfEdges(edges);
    }, [edges, setRfEdges]);

    // ---- SYNC: RF -> store (so selections/moves/connects persist) ----
    React.useEffect(() => {
        setNodes(rfNodes);
    }, [rfNodes, setNodes]);

    React.useEffect(() => {
        setEdges(rfEdges);
    }, [rfEdges, setEdges]);

    const onConnect = useCallback(
        (params: Edge | Connection) => {
            setRfEdges((eds) => addEdge({ ...params, animated: true }, eds));
        },
        [setRfEdges]
    );

    const nodeTypes: NodeTypes = useMemo(() => nodeTypesMap, []);

    // ---- NEW (Sprint 2): API-backed workflow persistence ----
    const workflowId = 1; // keep fixed for now; later can come from route/state
    const workflowName = "Demo Workflow";
    const { workflowQuery, saveWorkflow, updateWorkflow } = useWorkflow(workflowId);

    const onSave = async () => {
        validateWorkflow.parse({ nodes: rfNodes, edges: rfEdges });
        const payload = { name: workflowName, nodes: rfNodes, edges: rfEdges };
        try {
            if (workflowQuery.data) {
                await updateWorkflow.mutateAsync(payload);
            } else {
                await saveWorkflow.mutateAsync(payload);
            }
            alert("Saved ✨");
        } catch (e: any) {
            alert(`Save failed: ${e?.message || e}`);
        }
    };

    const onLoad = async () => {
        try {
            const data = workflowQuery.data ?? (await workflowQuery.refetch()).data;
            if (data) {
                setRfNodes((data as any).nodes ?? []);
                setRfEdges((data as any).edges ?? []);
            } else {
                alert("No saved workflow yet");
            }
        } catch (e: any) {
            alert(`Load failed: ${e?.message || e}`);
        }
    };

    const onSimulate = () => {
        validateWorkflow.parse({ nodes: rfNodes, edges: rfEdges });
        alert("Validation passed. (Runner coming next sprint)");
    };

    return (
        <div className="h-full grid grid-cols-[320px_1fr]">
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
                    <Button onClick={onSimulate}>Simulate</Button>
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
            <div className="h-full">
                <ReactFlow
                    nodes={rfNodes}
                    edges={rfEdges}
                    nodeTypes={nodeTypes}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={(_, n) => selectNode(n.id)}
                    fitView
                >
                    <MiniMap />
                    <Controls />
                    <Background gap={16} />
                </ReactFlow>
            </div>
        </div>
    );
}
