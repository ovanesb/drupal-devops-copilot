import * as React from "react";

type Status = "idle" | "running" | "success" | "error";

export default function StatusBadge({ status }: { status: Status }) {
    const config = {
        idle: {
            bg: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
            label: "Ready",
            icon: "⚪️",
        },
        running: {
            bg: "bg-drupal-100 text-drupal-700 dark:bg-drupal-900 dark:text-drupal-300 animate-pulse",
            label: "Running...",
            icon: "🔄",
        },
        success: {
            bg: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
            label: "Success",
            icon: "✅",
        },
        error: {
            bg: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
            label: "Error",
            icon: "❌",
        },
    };

    const { bg, label, icon } = config[status];

    return (
        <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1.5 ${bg}`}>
            <span>{icon}</span>
            <span>{label}</span>
        </span>
    );
}
