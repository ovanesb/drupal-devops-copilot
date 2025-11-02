import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";


export function useProfiles() {
    const qc = useQueryClient();


    const listQuery = useQuery({ queryKey: qk.profiles, queryFn: () => api.listProfiles() });


    const create = useMutation({
        mutationFn: (payload: { name: string; kind: string; base_url?: string; username?: string }) =>
            api.createProfile(payload),
        onSuccess: () => qc.invalidateQueries({ queryKey: qk.profiles }),
    });


    const update = useMutation({
        mutationFn: (args: { id: number; data: { name: string; kind: string; base_url?: string; username?: string } }) =>
            api.updateProfile(args.id, args.data),
        onSuccess: () => qc.invalidateQueries({ queryKey: qk.profiles }),
    });


    const remove = useMutation({
        mutationFn: (id: number) => api.deleteProfile(id),
        onSuccess: () => qc.invalidateQueries({ queryKey: qk.profiles }),
    });


    return { listQuery, create, update, remove };
}