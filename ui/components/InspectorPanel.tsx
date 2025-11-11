import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
    JiraTriggerNode,
    CreateMRNode,
    PlanPatchNode,
    CIWaitNode,
    DeployNode,
    QANode,
} from "@/lib/workflowSchema";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type AnyNodeLike = {
    id: string;
    type: string; // normalize below
    data: any;
};

const schemaMap = {
    JiraTrigger: JiraTriggerNode,
    CreateMR: CreateMRNode,
    PlanPatch: PlanPatchNode,
    CIWait: CIWaitNode,
    Deploy: DeployNode,
    QA: QANode,
} as const;

// normalize various casing/variants to canonical keys
function normalizeType(t: string): keyof typeof schemaMap | null {
    const key = t.replace(/[^a-z]/gi, "").toLowerCase();
    const map: Record<string, keyof typeof schemaMap> = {
        jiratrigger: "JiraTrigger",
        createmr: "CreateMR",  // handles CreateMr
        planpatch: "PlanPatch",
        ciwait: "CIWait",      // handles CiWait
        deploy: "Deploy",
        qa: "QA",              // handles Qa
    };
    return map[key] ?? null;
}

export default function InspectorPanel({
                                           selectedNode,
                                           onCommit,
                                       }: {
    selectedNode: (AnyNodeLike & { data: any }) | null;
    onCommit: (node: AnyNodeLike & { data: any }) => void;
}) {
    if (!selectedNode)
        return <div className="p-4 text-sm text-muted-foreground">Select a node.</div>;

    const canon = normalizeType(selectedNode.type);
    const schema = canon ? schemaMap[canon] : null;

    if (!schema) {
        return (
            <div className="p-4 text-sm">
                Unknown node type <code>{selectedNode.type}</code>.
                Expected one of: JiraTrigger, CreateMR, PlanPatch, CIWait, Deploy, QA.
            </div>
        );
    }

    const defaultValues = {
        ...selectedNode,
        data: {
            label: selectedNode.data?.label ?? canon,
            ...selectedNode.data,
        },
    };

    const form = useForm<any>({
        defaultValues,
        resolver: zodResolver(schema as any),
        mode: "onChange",
    });

    const submit = form.handleSubmit((values) => {
        const next = {
            id: selectedNode.id,
            type: selectedNode.type, // keep original type as RF expects
            data: { ...selectedNode.data, ...values.data },
            label: values.data?.label,
        };
        onCommit(next as any);
    });

    const placeholder = (canon ?? selectedNode.type ?? "") as string;

    return (
        <form onSubmit={submit} className="p-4 space-y-3">
            {/* Title bound to data.label */}
            <div>
                <Label>Title</Label>
                <Input {...form.register("data.label")} placeholder={placeholder} />

            </div>

            {canon === "JiraTrigger" && (
                <>
                    <Label>Project key</Label>
                    <Input {...form.register("data.projectKey")} />
                    <Label>JQL (optional)</Label>
                    <Input {...form.register("data.jql")} />
                    <Label>Label (optional)</Label>
                    <Input {...form.register("data.label")} />
                </>
            )}

            {canon === "CreateMR" && (
                <>
                    <Label>GitLab repo path</Label>
                    <Input {...form.register("data.repoPath")} placeholder="group/project" />
                    <Label>Branch pattern</Label>
                    <Input {...form.register("data.branchPattern")} />
                    <Label>Target branch</Label>
                    <Input {...form.register("data.targetBranch")} />
                </>
            )}

            {canon === "PlanPatch" && (
                <>
                    <Label>Scope</Label>
                    <Input {...form.register("data.scope")} />
                    <div className="flex items-center justify-between">
                        <Label>Guardrails</Label>
                        <Switch {...(form.register("data.guardrails") as any)} />
                    </div>
                    <div className="flex items-center justify-between">
                        <Label>Dry run</Label>
                        <Switch {...(form.register("data.dryRun") as any)} />
                    </div>
                </>
            )}

            {canon === "CIWait" && (
                <>
                    <Label>Pipeline URL (optional)</Label>
                    <Input {...form.register("data.pipelineUrl")} />
                    <Label>Timeout (sec)</Label>
                    <Input type="number" {...form.register("data.timeoutSec", { valueAsNumber: true })} />
                    <Label>Poll every (sec)</Label>
                    <Input type="number" {...form.register("data.pollSec", { valueAsNumber: true })} />
                </>
            )}

            {canon === "Deploy" && (
                <>
                    <Label>Environment</Label>
                    <Input {...form.register("data.environment")} />
                    <div className="flex items-center justify-between">
                        <Label>Safety checks</Label>
                        <Switch {...(form.register("data.safetyChecks") as any)} />
                    </div>
                </>
            )}

            {canon === "QA" && (
                <>
                    <Label>Checklist ref</Label>
                    <Input {...form.register("data.checklistRef")} />
                    <Label>Script ref</Label>
                    <Input {...form.register("data.scriptRef")} />
                </>
            )}

            <Button type="submit" className="w-full mt-2">Save</Button>
        </form>
    );
}
