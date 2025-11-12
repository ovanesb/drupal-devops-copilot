// ui/pages/api/run.ts
import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    const r = await fetch(`${backend}/api/run`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(req.body),
    });
    const data = await r.json();
    res.status(r.status).json(data);
}
