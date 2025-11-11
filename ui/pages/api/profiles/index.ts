import type { NextApiHandler } from "next";

type Profile = {
    id: string;
    kind: "jira" | "gitlab" | "acquia" | "generic";
    name: string;
    ref: string;
};

// Temporary in-memory store
const inmem: Profile[] = [];

const handler: NextApiHandler = (req, res) => {
    if (req.method === "GET") {
        return res.status(200).json(inmem);
    }

    if (req.method === "POST") {
        const raw = req.body;
        const body: Partial<Profile> =
            typeof raw === "string" ? JSON.parse(raw || "{}") : (raw ?? {});

        if (!body.id || !body.kind || !body.name || !body.ref) {
            return res.status(400).json({ error: "Missing required fields" });
        }
        inmem.push(body as Profile);
        return res.status(201).json(body);
    }

    res.setHeader("Allow", ["GET", "POST"]);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
};

export default handler;
