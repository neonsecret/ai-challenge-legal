"use client";

import {useTheme} from "next-themes";
import {useEffect, useState} from "react";

export function AppBackground({children}: { children: React.ReactNode }) {
    const {resolvedTheme} = useTheme();
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);

    const isDark = mounted && resolvedTheme === "dark";

    return (
        <div
            className="flex h-full w-full relative"
            style={{
                overflowX: "hidden",
                transition: "background 0.4s ease",
                background: isDark
                    ? "linear-gradient(145deg, #0d1520 0%, #0f1b2e 50%, #0a1120 100%)"
                    : "linear-gradient(145deg, #c8b080 0%, #d4be92 45%, #bca070 100%)",
            }}
        >
            {/* Fixed blobs */}
            <div aria-hidden style={{position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none"}}>
                {isDark ? (
                    <>
                        <div style={{
                            position: "absolute", width: 580, height: 580, top: -80, left: "8%",
                            background: "radial-gradient(circle, rgba(27,43,75,0.45) 0%, rgba(27,43,75,0.12) 45%, transparent 70%)"
                        }}/>
                        <div style={{
                            position: "absolute", width: 460, height: 460, top: 180, right: "4%",
                            background: "radial-gradient(circle, rgba(15,60,150,0.32) 0%, rgba(15,60,150,0.08) 45%, transparent 70%)"
                        }}/>
                        <div style={{
                            position: "absolute", width: 380, height: 380, bottom: 30, left: "28%",
                            background: "radial-gradient(circle, rgba(40,30,100,0.28) 0%, rgba(40,30,100,0.07) 45%, transparent 70%)"
                        }}/>
                    </>
                ) : (
                    <>
                        <div style={{
                            position: "absolute", width: 580, height: 580, top: -80, left: "8%",
                            background: "radial-gradient(circle, rgba(190,110,30,0.38) 0%, rgba(190,110,30,0.12) 45%, transparent 70%)"
                        }}/>
                        <div style={{
                            position: "absolute", width: 460, height: 460, top: 180, right: "4%",
                            background: "radial-gradient(circle, rgba(200,80,20,0.30) 0%, rgba(200,80,20,0.08) 45%, transparent 70%)"
                        }}/>
                        <div style={{
                            position: "absolute", width: 380, height: 380, bottom: 30, left: "28%",
                            background: "radial-gradient(circle, rgba(175,130,20,0.26) 0%, rgba(175,130,20,0.07) 45%, transparent 70%)"
                        }}/>
                    </>
                )}
            </div>

            {children}
        </div>
    );
}
