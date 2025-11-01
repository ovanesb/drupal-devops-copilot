"use client";
import { useMutation, useQuery } from "@tanstack/react-query";

export function useSaveWorkflow() {
    return useMutation({
        mutationFn: async (payload: any) => {
            // placeholder: call FastAPI later; for now, persist in localStorage
            if (typeof window !== "undefined") localStorage.setItem(`wf:${payload.id}`, JSON.stringify(payload));
            return payload;
        },
    });
}

export function useLoadWorkflow(id: string) {
    return useQuery({
        queryKey: ["workflow", id],
        queryFn: async () => {
            if (typeof window === "undefined") return null;
            const s = localStorage.getItem(`wf:${id}`);
            return s ? JSON.parse(s) : null;
        },
    });
}