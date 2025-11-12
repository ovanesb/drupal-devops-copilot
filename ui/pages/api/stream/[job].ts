// ui/pages/api/stream/[job].ts
import type { NextApiRequest, NextApiResponse } from "next";

// helps with streaming
export const config = { runtime: "edge" };

export default async function handler(req: NextApiRequest) {
    // Next.js Edge handlers use Web Fetch API Response instead of res.send
    const job = Array.isArray(req.query.job) ? req.query.job[0] : req.query.job;
    const backend = process.env.BACKEND_URL || "http://localhost:8000";

    const resp = await fetch(`${backend}/api/stream/${job}`, { cache: "no-store" });
    if (!resp.ok || !resp.body) {
        return new Response("stream not available", { status: 502 });
    }

    return new Response(resp.body, {
        headers: { "Content-Type": "text/event-stream" },
    });
}
