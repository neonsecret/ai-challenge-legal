"use client";

import { Sun, Moon, Monitor } from "lucide-react";
import { useColorMode, type ColorMode } from "@/lib/color-mode";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const CYCLE: Record<ColorMode, ColorMode> = { light: "dark", dark: "system", system: "light" };

const LABELS: Record<ColorMode, string> = {
    light: "Light mode",
    dark: "Dark mode",
    system: "System preference",
};

const ICONS: Record<ColorMode, typeof Sun> = {
    light: Sun,
    dark: Moon,
    system: Monitor,
};

export function ThemeToggle() {
    const { mode, setMode } = useColorMode();
    const Icon = ICONS[mode];

    return (
        <Tooltip>
            <TooltipTrigger>
                <button
                    onClick={() => setMode(CYCLE[mode])}
                    aria-label={`Switch theme (currently ${LABELS[mode]})`}
                    style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 28,
                        height: 28,
                        borderRadius: 6,
                        border: "1px solid transparent",
                        background: "transparent",
                        color: "var(--strict-text-dim, currentColor)",
                        cursor: "pointer",
                        transition: "background 0.15s, border-color 0.15s, color 0.15s",
                    }}
                    onMouseEnter={e => {
                        const el = e.currentTarget;
                        el.style.background = "rgba(201,168,76, 0.05)";
                        el.style.borderColor = "var(--strict-gold-border, rgba(201,168,76,0.12))";
                        el.style.color = "var(--strict-text-secondary, currentColor)";
                    }}
                    onMouseLeave={e => {
                        const el = e.currentTarget;
                        el.style.background = "transparent";
                        el.style.borderColor = "transparent";
                        el.style.color = "var(--strict-text-dim, currentColor)";
                    }}
                >
                    <Icon size={14} />
                </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
                <p>{LABELS[mode]}</p>
            </TooltipContent>
        </Tooltip>
    );
}
