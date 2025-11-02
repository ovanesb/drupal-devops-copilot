export const API_BASE =
    process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

// ---- Types ----
export type JsonObject = Record<string, any>;

export type WorkflowPayload = {
    name: string;
    nodes: JsonObject | any[];
    edges: JsonObject | any[];
};

export type Workflow = WorkflowPayload & {
    id: number;
    created_at: string;
    updated_at: string;
};

export type ProfilePayload = {
    name: string;
    kind: "jira" | "gitlab" | "acquia" | "custom" | (string & {});
    base_url?: string;
    username?: string;
};

export type Profile = ProfilePayload & {
    id: number;
    created_at: string;
    updated_at: string;
};

// ---- HTTP helper ----
async function http<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        ...options,
    });

    if (!res.ok) {
        const msg = await safeText(res);
        throw new Error(msg || `HTTP ${res.status}`);
    }

    // Some DELETEs may return empty body; guard that
    if (res.status === 204) return undefined as unknown as T;
    return res.json() as Promise<T>;
}

async function safeText(res: Response) {
    try {
        return await res.text();
    } catch {
        return "";
    }
}

// ---- API surface ----
export const api = {
    // Workflows
    getWorkflow: (id: number) => http<Workflow>(`/workflows/${id}`),
    postWorkflow: (id: number, data: WorkflowPayload) =>
        http<Workflow>(`/workflows/${id}`, {
            method: "POST",
            body: JSON.stringify(data),
        }),
    putWorkflow: (id: number, data: WorkflowPayload) =>
        http<Workflow>(`/workflows/${id}`, {
            method: "PUT",
            body: JSON.stringify(data),
        }),

    // Profiles
    listProfiles: () => http<Profile[]>(`/profiles`),
    createProfile: (data: ProfilePayload) =>
        http<Profile>(`/profiles`, { method: "POST", body: JSON.stringify(data) }),
    updateProfile: (id: number, data: ProfilePayload) =>
        http<Profile>(`/profiles?id=${id}`, {
            method: "PUT",
            body: JSON.stringify(data),
        }),
    deleteProfile: (id: number) =>
        http<{ ok: true }>(`/profiles?id=${id}`, { method: "DELETE" }),
};
