'use client'

import {
    Card,
    CardHeader,
    CardFooter,
    CardTitle,
    CardAction,
    CardDescription,
    CardContent,
} from "@/components/ui/card"
import {cn} from "@/lib/utils"

interface GlassCardProps extends React.ComponentProps<"div"> {
    variant?: "panel" | "subtle" | "heavy" | "gold"
    accent?: boolean
    children: React.ReactNode
}

const variantMap = {
    panel: "glass-md shadow-glass rounded-2xl",
    subtle: "glass-sm shadow-glass-sm rounded-xl",
    heavy: "glass-lg shadow-glass-xl rounded-2xl",
    gold: "glass-gold shadow-glass rounded-2xl",
} as const

const hoverMap = {
    panel: "",
    subtle: "",
    heavy: "hover:shadow-glass-xl hover:translate-y-[-2px] transition-transform duration-200",
    gold: "hover:border-[rgba(201,168,76,0.45)] transition-colors duration-150",
} as const

export function GlassCard({
                              variant = "panel",
                              accent = false,
                              className,
                              children,
                              ...props
                          }: GlassCardProps) {
    return (
        <div className={cn("overflow-clip relative", accent && "glass-top-accent", className)}>
            <Card
                className={cn(
                    "[background:none] border-0 ring-0 [overflow:visible]",
                    variantMap[variant],
                    hoverMap[variant]
                )}
                {...props}
            >
                {children}
            </Card>
        </div>
    )
}

export {
    CardHeader,
    CardFooter,
    CardTitle,
    CardAction,
    CardDescription,
    CardContent,
}
