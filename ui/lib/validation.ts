import { z } from "zod";
export const NodeSchema = z.object({ id: z.string(), type: z.string(), position: z.object({ x: z.number(), y: z.number() }), data: z.any() });
export const EdgeSchema = z.object({ id: z.string().optional(), source: z.string(), target: z.string() });
export const validateWorkflow = z.object({ nodes: z.array(NodeSchema).min(1, "At least one node"), edges: z.array(EdgeSchema) });