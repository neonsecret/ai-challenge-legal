// Importing the React default export forces eager Turbopack module evaluation.
// See global-error.tsx for the full explanation.
import React from "react";
import Link from "next/link";

export default function NotFound() {
    return (
        <div
            style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: "60vh",
                fontFamily: "system-ui, sans-serif",
            }}
        >
            <h1 style={{fontSize: "2rem", fontWeight: 700, marginBottom: "8px"}}>
                404
            </h1>
            <p style={{opacity: 0.6}}>Page not found</p>
            <Link href="/" style={{marginTop: "16px", opacity: 0.8, textDecoration: "underline", display: "inline-flex", alignItems: "center", minHeight: "44px", padding: "0 8px"}}>
                Go home
            </Link>
        </div>
    );
}
