"use client";
import { create } from "zustand";
import type { Edge, Node } from "@xyflow/react";

export type IntegrationProfile = {
    id: string;
    name: string;
    kind: "jira" | "gitlab" | "acquia" | "generic";
    baseUrl?: string;
    username?: string;
};

type FlowState = {
    nodes: Node[];
    edges: Edge[];
    profiles: IntegrationProfile[];

    setNodes: (n: Node[]) => void;
    setEdges: (e: Edge[]) => void;
    addNode: (n: Node) => void;

    addProfile: (p: IntegrationProfile) => void;
    attachProfileToNode: (nodeId: string, profileId: string) => void;

    reset: () => void;
    selectNode: (id: string) => void;
};

export const useFlowStore = create<FlowState>((set, get) => ({
    nodes: [],
    edges: [],
    profiles: [],

    setNodes: (nodes) => set({ nodes }),
    setEdges: (edges) => set({ edges }),
    addNode: (n) => set({ nodes: [...get().nodes, n] }),

    addProfile: (p) => set({ profiles: [...get().profiles, p] }),
    attachProfileToNode: (nodeId, profileId) =>
        set({
            nodes: get().nodes.map((n) =>
                n.id === nodeId ? { ...n, data: { ...n.data, profileId } } : n
            ),
        }),

    reset: () => set({ nodes: [], edges: [] }),
    selectNode: (id) =>
        set({
            nodes: get().nodes.map((n) => ({ ...n, selected: n.id === id })),
        }),
}));
