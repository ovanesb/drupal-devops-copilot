import * as React from "react";

export default function DarkModeToggle() {
    const [darkMode, setDarkMode] = React.useState(false);

    React.useEffect(() => {
        const isDark = localStorage.getItem("darkMode") === "true";
        setDarkMode(isDark);
        if (isDark) {
            document.documentElement.classList.add("dark");
        }
    }, []);

    const toggle = () => {
        const newMode = !darkMode;
        setDarkMode(newMode);
        localStorage.setItem("darkMode", String(newMode));
        if (newMode) {
            document.documentElement.classList.add("dark");
        } else {
            document.documentElement.classList.remove("dark");
        }
    };

    return (
        <button
            onClick={toggle}
            className="px-4 py-2.5 rounded-lg bg-white/20 hover:bg-white/30 backdrop-blur-sm transition-all duration-200 text-white font-medium shadow-lg hover:shadow-xl flex items-center gap-2"
            title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
        >
            <span className="text-xl">{darkMode ? "☀️" : "🌙"}</span>
            <span className="hidden sm:inline">{darkMode ? "Light" : "Dark"}</span>
        </button>
    );
}
