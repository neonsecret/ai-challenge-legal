"use client";

/**
 * AuroraBackground — V3 "Strict" animated aurora for the landing page only.
 *
 * Contains animated orbs + cursor ambient light. Do NOT render this in the
 * workspace layout — use `.aurora-bg-static` there instead.
 *
 * Wraps children so they render above the aurora layer (z-index: 1+).
 * Respects `prefers-reduced-motion` via CSS and disables cursor tracking.
 */

import { useEffect, useRef } from "react";

interface AuroraBackgroundProps {
    children: React.ReactNode;
    className?: string;
}

export function AuroraBackground({ children, className = "" }: AuroraBackgroundProps) {
    const rafRef = useRef<number | null>(null);

    useEffect(() => {
        const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
        if (mq.matches) return;

        const handleMouseMove = (e: MouseEvent) => {
            if (rafRef.current !== null) return;
            rafRef.current = requestAnimationFrame(() => {
                document.documentElement.style.setProperty("--cursor-x", `${e.clientX}px`);
                document.documentElement.style.setProperty("--cursor-y", `${e.clientY}px`);
                rafRef.current = null;
            });
        };

        window.addEventListener("mousemove", handleMouseMove, { passive: true });
        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
        };
    }, []);

    return (
        <div className={`aurora-bg relative ${className}`}>
            {/* Cursor ambient light — landing page only */}
            <div className="ambient-cursor" aria-hidden="true" />

            {/* Aurora orbs — floating gaussian blobs */}
            <div className="v3-orb v3-orb-1" aria-hidden="true" />
            <div className="v3-orb v3-orb-2" aria-hidden="true" />
            <div className="v3-orb v3-orb-3" aria-hidden="true" />

            {/* Content — above aurora layer */}
            <div className="relative" style={{ zIndex: 1 }}>
                {children}
            </div>
        </div>
    );
}
