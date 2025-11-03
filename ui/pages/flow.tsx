import React from "react";
import FlowBuilder from "@/components/FlowBuilder";

export default function FlowPage() {
    return (
        <div
            style={{
                height: "100vh",     // full screen height
                width: "100vw",      // full screen width
                overflow: "hidden",  // avoids scrollbars interfering with RF pane
            }}
        >
            <FlowBuilder />
        </div>
    );
}
