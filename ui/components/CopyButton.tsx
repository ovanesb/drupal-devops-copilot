import * as React from "react";

export default function CopyButton({ text }: { text: string }) {
    const [copied, setCopied] = React.useState(false);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy:", err);
        }
    };

    return (
        <button
            onClick={copy}
            className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 dark:bg-gray-600 dark:hover:bg-gray-500 text-white rounded transition-colors"
            title="Copy logs to clipboard"
        >
            {copied ? "✓ Copied!" : "📋 Copy"}
        </button>
    );
}
