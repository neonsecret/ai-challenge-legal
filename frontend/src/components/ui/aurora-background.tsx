import {cn} from "@/lib/utils"

interface AuroraBackgroundProps {
    preset: "chat" | "landing" | "app-subtle"
    className?: string
}

interface OrbConfig {
    color: string
    size: string
    position: Record<string, string>
    opacity: number
    blurClass: string
}

const presets: Record<AuroraBackgroundProps["preset"], OrbConfig[]> = {
    chat: [
        {
            color: "var(--orb-gold-color)",
            size: "clamp(500px, 65vw, 900px)",
            position: {top: "-15%", right: "-10%"},
            opacity: 0.45,
            blurClass: "orb-blur-xl",
        },
        {
            color: "var(--orb-blue-color)",
            size: "clamp(400px, 55vw, 700px)",
            position: {bottom: "-15%", left: "-10%"},
            opacity: 0.40,
            blurClass: "orb-blur-2xl",
        },
        {
            color: "var(--orb-teal-color)",
            size: "clamp(280px, 38vw, 480px)",
            position: {bottom: "-10%", right: "15%"},
            opacity: 0.35,
            blurClass: "orb-blur-lg",
        },
    ],
    landing: [
        {
            color: "var(--orb-gold-color)",
            size: "clamp(400px, 55vw, 750px)",
            position: {top: "-20%", right: "-5%"},
            opacity: 0.40,
            blurClass: "orb-blur-xl",
        },
        {
            color: "var(--orb-navy-color)",
            size: "clamp(450px, 60vw, 800px)",
            position: {bottom: "-20%", left: "-15%"},
            opacity: 0.50,
            blurClass: "orb-blur-2xl",
        },
    ],
    "app-subtle": [
        {
            color: "var(--orb-gold-color)",
            size: "clamp(300px, 42vw, 600px)",
            position: {top: "-15%", right: "5%"},
            opacity: 0.25,
            blurClass: "orb-blur-xl",
        },
        {
            color: "var(--orb-blue-color)",
            size: "clamp(350px, 45vw, 550px)",
            position: {bottom: "-10%", left: "-5%"},
            opacity: 0.20,
            blurClass: "orb-blur-2xl",
        },
    ],
}

/**
 * AuroraBackground renders colored orb divs as a decorative background layer.
 * Place as a sibling (not wrapper) inside a relative container.
 *
 * @example
 * ```tsx
 * <div className="relative min-h-screen page-dark">
 *   <AuroraBackground preset="chat" />
 *   <div className="relative z-10">{content}</div>
 * </div>
 * ```
 */
export function AuroraBackground({preset, className}: AuroraBackgroundProps) {
    const orbs = presets[preset]

    return (
        <div className={cn("aurora-container", className)} aria-hidden="true">
            {orbs.map((orb, i) => (
                <div
                    key={i}
                    className={cn("absolute rounded-full", orb.blurClass)}
                    style={{
                        width: orb.size,
                        height: orb.size,
                        ...orb.position,
                        background: orb.color,
                        opacity: orb.opacity,
                    }}
                />
            ))}
        </div>
    )
}
