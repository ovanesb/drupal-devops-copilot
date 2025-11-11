import { z } from "zod";

export const BaseProfile = z.object({
    id: z.string().uuid(),
    kind: z.enum(["jira","gitlab","acquia","generic"]),
    name: z.string().min(1),
    // store only references/aliases in UI; secrets live in backend vault
    ref: z.string().min(1), // e.g., "JIRA_DEFAULT", "GL_MAIN", "ACQUIA_STG"
});
export type BaseProfile = z.infer<typeof BaseProfile>;
