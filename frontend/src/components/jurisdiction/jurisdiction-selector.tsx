"use client";

import {useState, useRef, useEffect} from "react";
import {ChevronDown} from "lucide-react";
import {useJurisdiction} from "@/lib/use-jurisdiction";
import {
    JURISDICTIONS,
    JURISDICTION_ORDER,
    type Jurisdiction,
} from "@/lib/jurisdictions";
import {cn} from "@/lib/utils";

interface JurisdictionSelectorProps {
    compact?: boolean;
    className?: string;
}

export function JurisdictionSelector({
                                         compact = false,
                                         className,
                                     }: JurisdictionSelectorProps) {
    const {jurisdiction, setJurisdiction} = useJurisdiction();
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const current = JURISDICTIONS[jurisdiction];

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    return (
        <div ref={ref} className={cn("relative", className)}>
            <button
                onClick={() => setOpen((v) => !v)}
                className={cn(
                    "flex items-center gap-1.5 rounded-md text-xs font-medium transition-colors",
                    "border border-sidebar-border bg-sidebar-accent/30 hover:bg-sidebar-accent",
                    "text-sidebar-foreground/70 hover:text-sidebar-foreground",
                    compact ? "px-2 py-1" : "px-3 py-1.5"
                )}
            >
                <JurisdictionCode
                    code={current.code}
                    color={current.color}
                    size="sm"
                />
                {!compact && (
                    <span className="truncate max-w-[120px]">{current.name}</span>
                )}
                <ChevronDown
                    className={cn("size-3 shrink-0 transition-transform", open && "rotate-180")}
                />
            </button>

            {open && (
                <div
                    className="absolute left-0 top-full mt-1 z-50 min-w-[220px] rounded-lg border border-border bg-popover shadow-lg overflow-hidden">
                    {JURISDICTION_ORDER.map((key) => {
                        const config = JURISDICTIONS[key];
                        const isActive = jurisdiction === key;
                        return (
                            <button
                                key={key}
                                onClick={() => {
                                    setJurisdiction(key);
                                    setOpen(false);
                                }}
                                className={cn(
                                    "w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-left transition-colors",
                                    isActive
                                        ? "bg-muted text-foreground"
                                        : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                                )}
                            >
                                <JurisdictionCode
                                    code={config.code}
                                    color={config.color}
                                    size="md"
                                />
                                <div className="flex-1 min-w-0">
                                    <div className="font-medium text-xs">{config.name}</div>
                                    <div className="text-[11px] text-muted-foreground/70 truncate">
                                        {config.description}
                                    </div>
                                </div>
                                {isActive && (
                                    <span
                                        className="size-1.5 rounded-full shrink-0"
                                        style={{backgroundColor: config.color}}
                                    />
                                )}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

interface JurisdictionCodeProps {
    code: string;
    color: string;
    size?: "sm" | "md";
}

export function JurisdictionCode({
                                     code,
                                     color,
                                     size = "md",
                                 }: JurisdictionCodeProps) {
    return (
        <span
            className={cn(
                "inline-flex items-center justify-center rounded font-bold tracking-wider shrink-0",
                size === "sm" ? "text-[9px] px-1 py-0.5 min-w-[20px]" : "text-[10px] px-1.5 py-0.5 min-w-[26px]"
            )}
            style={{
                backgroundColor: color + "22",
                color: color,
                border: `1px solid ${color}44`,
            }}
        >
      {code}
    </span>
    );
}

/** Standalone badge variant — not a selector, just a display badge */
export function JurisdictionBadge({
                                      jurisdiction,
                                      className,
                                  }: {
    jurisdiction: Jurisdiction;
    className?: string;
}) {
    const config = JURISDICTIONS[jurisdiction];
    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 rounded-md text-xs font-medium px-2 py-0.5",
                className
            )}
            style={{
                backgroundColor: config.color + "18",
                color: config.color,
                border: `1px solid ${config.color}33`,
            }}
        >
      <JurisdictionCode code={config.code} color={config.color} size="sm"/>
            {config.name}
    </span>
    );
}
