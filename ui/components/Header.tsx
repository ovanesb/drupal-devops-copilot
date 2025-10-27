import * as React from "react";
import DarkModeToggle from "./DarkModeToggle";

export default function Header() {
    return (
        <div className="bg-drupal-gradient dark:bg-drupal-gradient-dark text-white shadow-lg mb-8 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-8">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="text-5xl">🚀</div>
                    <div>
                        <h1 className="text-4xl font-bold mb-2">
                            Drupal DevOps Co-Pilot
                        </h1>
                        <p className="text-drupal-50 text-lg">
                            Run the full flow in one click or step through each stage independently — all with live streaming logs.
                        </p>
                    </div>
                </div>
                <DarkModeToggle />
            </div>
        </div>
    );
}
