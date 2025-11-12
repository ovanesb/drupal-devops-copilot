import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    const url = `${backend}/api/workflows`;

    const r = await fetch(url, {
        method: req.method,
        headers: { "content-type": "application/json" },
        body: ["PUT", "POST", "PATCH"].includes(req.method || "") ? JSON.stringify(req.body) : undefined,
    });

    const text = await r.text();
    const contentType = r.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? JSON.parse(text || "{}") : text;

    res.status(r.status).send(data);
}
