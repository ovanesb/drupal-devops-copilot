import "@/styles/globals.css";
import type { AppProps } from "next/app";
import React from "react";
import Head from "next/head";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export default function App({ Component, pageProps }: AppProps) {
    // one QueryClient for the entire app lifecycle
    const [qc] = React.useState(() => new QueryClient());

    return (
        <>
            {/* Optional: set a default title/description.
          Remove or override per-page with next/head in each page. */}
            <Head>
                <title>Drupal DevOps Co-Pilot — Flow Builder</title>
                <meta name="description" content="Drag-and-drop workflow editor" />
            </Head>

            <QueryClientProvider client={qc}>
                {/* Global layout classes used by the Flow UI theme */}
                <div className="min-h-screen bg-background text-foreground antialiased">
                    <Component {...pageProps} />
                </div>
            </QueryClientProvider>
        </>
    );
}
