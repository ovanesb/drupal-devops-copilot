import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";

export function useWorkflow(id: number) {
    const qc = useQueryClient();

    const workflowQuery = useQuery({
        queryKey: qk.workflow(id),
        queryFn: () => api.getWorkflow(id),
        // optional: avoid retry loops if 404 is expected for new installs
        retry: false,
    });

    const saveWorkflow = useMutation({
        mutationFn: (payload: { name: string; nodes: any; edges: any }) =>
            api.postWorkflow(id, payload),
        onSuccess: (data) => {
            qc.setQueryData(qk.workflow(id), data);
        },
    });

    const updateWorkflow = useMutation({
        mutationFn: (payload: { name: string; nodes: any; edges: any }) =>
            api.putWorkflow(id, payload),
        onSuccess: (data) => {
            qc.setQueryData(qk.workflow(id), data);
        },
    });

    return { workflowQuery, saveWorkflow, updateWorkflow };
}
