import * as React from "react";
import DarkModeToggle from "./DarkModeToggle";

export default function Header() {
    return (
        <header className="bg-drupal-gradient dark:bg-drupal-gradient-dark shadow-xl mb-8 px-4 sm:px-6 lg:px-8 py-8 rounded-2xl" role="banner">
            <div className="flex justify-between items-center gap-6 flex-wrap">
                <div className="flex items-center gap-4">
                    <div className="text-5xl" role="img" aria-label="Rocket">🚀</div>
                    <div>
                        <h1 className="text-4xl font-bold mb-2 text-white">
                            Drupal DevOps Co-Pilot
                        </h1>
                        <p className="text-white text-lg font-medium">
                            Run the full flow in one click or step through each stage independently — all with live streaming logs.
                        </p>
                    </div>
                </div>
                <DarkModeToggle />
            </div>
        </header>
    );
}
