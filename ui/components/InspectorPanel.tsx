import { z } from "zod";
import { useEffect } from "react";
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
    type: string;
    position?: { x: number; y: number };
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
        createmr: "CreateMR", // handles CreateMr
        planpatch: "PlanPatch",
        ciwait: "CIWait", // handles CiWait
        deploy: "Deploy",
        qa: "QA", // handles Qa
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
    console.log(
        "[Inspector render] selectedNode=",
        selectedNode.id,
        selectedNode.type,
        selectedNode.data
    );
    const canon = normalizeType(selectedNode.type);
    const schema = canon ? schemaMap[canon] : null;

    if (!schema) {
        return (
            <div className="p-4 text-sm">
                Unknown node type <code>{selectedNode.type}</code>. Expected one of: JiraTrigger,
                CreateMR, PlanPatch, CIWait, Deploy, QA.
            </div>
        );
    }

    // Build a form schema that matches our form shape: { data: <nodeDataSchema> }
    const formSchema = z.object({ data: (schema as unknown as z.ZodTypeAny) });

    const form = useForm<any>({
        defaultValues: {
            data: {
                label: selectedNode.data?.label ?? (selectedNode.type || "Node"),
                ...selectedNode.data,
            },
        },
        resolver: zodResolver(formSchema),
        mode: "onChange",
    });


    // keep form in sync when the selection changes
    useEffect(() => {
        if (!selectedNode) return;
        form.reset({
            data: {
                label: selectedNode.data?.label ?? (selectedNode.type || "Node"),
                ...selectedNode.data,
            },
        });
    }, [selectedNode, form]);

    // Submit merges values into node.data and returns full node shape
    const onSubmit = (values: any) => {
        if (!selectedNode) return;

        const mergedData = {
            ...(selectedNode.data ?? {}),
            ...(values?.data ?? values),
            label:
                values?.data?.label ??
                values?.label ??
                selectedNode.data?.label ??
                selectedNode.type,
        };

        const next = {
            id: selectedNode.id,
            type: selectedNode.type,
            position: selectedNode.position,
            data: mergedData,
        };

        console.log("[Inspector submit] values=", values, "next=", next);
        onCommit(next as any);

        if (typeof window !== "undefined") {
            // replace with toast later
            // eslint-disable-next-line no-alert
            alert("Node updated");
        }
    };

    const placeholder = (canon ?? selectedNode.type ?? "") as string;

    return (
        <form onSubmit={form.handleSubmit(onSubmit)} className="p-4 space-y-3">
            {/* Title bound to data.label */}
            <div>
                <Label>Title</Label>
                <Input {...form.register("data.label")} placeholder={placeholder} />
            </div>

            {canon === "JiraTrigger" && (
                <>
                    <Label>Project key</Label>
                    <Input {...form.register("data.projectKey")} placeholder="CCS" />
                    <Label>JQL (optional)</Label>
                    <Input
                        {...form.register("data.jql")}
                        placeholder='project = CCS AND status = "In Progress"'
                    />
                    <Label>Label (optional)</Label>
                    {/* use labelFilter to avoid clashing with Title */}
                    <Input {...form.register("data.labelFilter")} placeholder="CCS-1234" />
                </>
            )}

            {canon === "CreateMR" && (
                <>
                    <Label>GitLab repo path</Label>
                    <Input {...form.register("data.repoPath")} placeholder="group/project" />
                    <Label>Branch pattern</Label>
                    <Input
                        {...form.register("data.branchPattern")}
                        placeholder="feature/{JIRA}"
                    />
                    <Label>Target branch</Label>
                    <Input {...form.register("data.targetBranch")} placeholder="master" />
                </>
            )}

            {canon === "PlanPatch" && (
                <>
                    <Label>Scope</Label>
                    <Input {...form.register("data.scope")} placeholder="modules/custom" />
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
                    <Input
                        {...form.register("data.pipelineUrl")}
                        placeholder="https://gitlab.com/..."
                    />
                    <Label>Timeout (sec)</Label>
                    <Input
                        type="number"
                        {...form.register("data.timeoutSec", { valueAsNumber: true })}
                    />
                    <Label>Poll every (sec)</Label>
                    <Input
                        type="number"
                        {...form.register("data.pollSec", { valueAsNumber: true })}
                    />
                </>
            )}

            {canon === "Deploy" && (
                <>
                    <Label>Environment</Label>
                    <Input {...form.register("data.environment")} placeholder="stg" />
                    <div className="flex items-center justify-between">
                        <Label>Safety checks</Label>
                        <Switch {...(form.register("data.safetyChecks") as any)} />
                    </div>
                </>
            )}

            {canon === "QA" && (
                <>
                    <Label>Checklist ref</Label>
                    <Input
                        {...form.register("data.checklistRef")}
                        placeholder="default-qa-checks"
                    />
                    <Label>Script ref</Label>
                    <Input
                        {...form.register("data.scriptRef")}
                        placeholder="qa/drush-smoke.sh"
                    />
                </>
            )}

            <Button
                type="button"
                className="w-full mt-2"
                onClick={() => {
                    console.log("[Inspector] Save button clicked");
                    form.handleSubmit(
                        onSubmit,
                        (errors) => {
                            console.warn("[Inspector] validation errors:", errors);
                            const vals = form.getValues();
                            console.log("[Inspector] forcing save with raw values", vals);
                            // Fallback: force-commit raw values so we can verify persistence path end-to-end
                            onSubmit(vals);
                        }
                    )();
                }}
            >
                Save node
            </Button>


        </form>
    );
}
