import { z } from "zod";

/** Shared */
export const ProfileRef = z.object({
    id: z.string().uuid(),
    kind: z.enum(["jira","gitlab","acquia","generic"]),
    name: z.string().min(1),
});

export const BaseNode = z.object({
    id: z.string(),
    type: z.enum(["JiraTrigger","CreateMR","PlanPatch","CIWait","Deploy","QA"]),
    position: z.object({ x: z.number(), y: z.number() }),
    label: z.string().default(""),
    profile: ProfileRef.optional(),    // attach/detach
});

export const JiraTriggerNode = BaseNode.extend({
    type: z.literal("JiraTrigger"),
    data: z.object({
        projectKey: z.string().min(1),
        jql: z.string().optional(),
        label: z.string().optional(),
    }),
});

export const CreateMRNode = BaseNode.extend({
    type: z.literal("CreateMR"),
    data: z.object({
        repoPath: z.string().min(1),   // group/project
        branchPattern: z.string().default("feature/{JIRA}"),
        targetBranch: z.string().default("master"),
    }),
});

export const PlanPatchNode = BaseNode.extend({
    type: z.literal("PlanPatch"),
    data: z.object({
        scope: z.enum(["modules/custom","repo"]).default("modules/custom"),
        guardrails: z.boolean().default(true),
        dryRun: z.boolean().default(true),
    }),
});

export const CIWaitNode = BaseNode.extend({
    type: z.literal("CIWait"),
    data: z.object({
        pipelineUrl: z.string().url().optional(),
        timeoutSec: z.number().int().min(30).max(60*60).default(900),
        pollSec: z.number().int().min(3).max(60).default(10),
    }),
});

export const DeployNode = BaseNode.extend({
    type: z.literal("Deploy"),
    data: z.object({
        environment: z.enum(["dev","stg","prod"]).default("stg"),
        safetyChecks: z.boolean().default(true),
    }),
});

export const QANode = BaseNode.extend({
    type: z.literal("QA"),
    data: z.object({
        checklistRef: z.string().optional(),
        scriptRef: z.string().optional(),
    }),
});

export const AnyNode = z.discriminatedUnion("type", [
    JiraTriggerNode, CreateMRNode, PlanPatchNode, CIWaitNode, DeployNode, QANode
]);

export const Edge = z.object({
    id: z.string(),
    source: z.string(),
    target: z.string(),
});

export const WorkflowV1 = z.object({
    version: z.literal("v1"),
    name: z.string().min(1),
    nodes: z.array(AnyNode),
    edges: z.array(Edge),
});
export type WorkflowV1 = z.infer<typeof WorkflowV1>;
export type AnyNode = z.infer<typeof AnyNode>;
