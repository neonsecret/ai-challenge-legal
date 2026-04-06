// Importing the React default export forces eager Turbopack module evaluation.
// See global-error.tsx for the full explanation.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import React from "react";

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
            <a href="/" style={{marginTop: "16px", opacity: 0.8, textDecoration: "underline"}}>
                Go home
            </a>
        </div>
    );
}
