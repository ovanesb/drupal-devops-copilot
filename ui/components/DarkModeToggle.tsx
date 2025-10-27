import * as React from "react";

export default function DarkModeToggle() {
    const [darkMode, setDarkMode] = React.useState(false);
    const [mounted, setMounted] = React.useState(false);

    React.useEffect(() => {
        setMounted(true);
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

    // Avoid hydration mismatch
    if (!mounted) {
        return <div className="w-[100px] h-[42px]" aria-hidden="true" />;
    }

    return (
        <button
            onClick={toggle}
            className="px-4 py-2.5 rounded-lg bg-white/25 hover:bg-white/40 backdrop-blur-sm transition-all duration-200 text-white font-semibold shadow-lg hover:shadow-xl flex items-center gap-2 border border-white/30 focus:outline-none focus:ring-2 focus:ring-white/50"
            aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
            title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
        >
            <span className="text-xl" role="img" aria-hidden="true">{darkMode ? "☀️" : "🌙"}</span>
            <span className="hidden sm:inline">{darkMode ? "Light" : "Dark"}</span>
        </button>
    );
}
