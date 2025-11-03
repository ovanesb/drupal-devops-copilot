import { create } from "zustand";
import type { Edge, Node } from "@xyflow/react";

export type NodeTypeId =
    | "jiraTrigger"
    | "createMR"
    | "planPatch"
    | "ciWait"
    | "deploy"
    | "qa";

type FlowState = {
    nodes: Node[];
    edges: Edge[];
    // selected node id (optional UX)
    selectedId?: string | null;

    // core setters (already used by FlowBuilder)
    setNodes: (nodes: Node[]) => void;
    setEdges: (edges: Edge[]) => void;

    // helpers
    reset: () => void;
    selectNode: (id: string | null) => void;

    // NEW: add a node (used by Palette click)
    addNode: (type: NodeTypeId, position?: { x: number; y: number }) => void;
};

export const useFlowStore = create<FlowState>((set, get) => ({
    nodes: [],
    edges: [],
    selectedId: null,

    setNodes: (nodes) => set({ nodes }),
    setEdges: (edges) => set({ edges }),

    reset: () => set({ nodes: [], edges: [], selectedId: null }),
    selectNode: (id) => set({ selectedId: id }),

    addNode: (type, position) => {
        const id = crypto.randomUUID();
        const offset = (get().nodes?.length ?? 0) * 40;
        const pos = position ?? { x: 420 + offset, y: 200 };

        const n: Node = {
            id,
            type,
            position: pos,
            data: {
                label: type,
                profileId: null,
                config: {},
            },
        };

        set((s) => ({ nodes: [...(s.nodes || []), n] }));
    },
}));
