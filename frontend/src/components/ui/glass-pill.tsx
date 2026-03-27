'use client'

import { cn } from "@/lib/utils"

interface GlassPillProps {
  variant?: "default" | "gold" | "error" | "success"
  size?: "sm" | "md"
  className?: string
  children: React.ReactNode
  onClick?: React.MouseEventHandler<HTMLButtonElement>
  disabled?: boolean
}

const variantMap = {
  default: "glass-pill-default",
  gold:    "glass-pill-gold",
  error:   "glass-pill-error",
  success: "glass-pill-success",
} as const

const sizeMap = {
  sm: "px-[10px] py-[4px] text-[0.75rem] min-h-[28px]",
  md: "px-[14px] py-[6px] text-[0.8125rem] min-h-[32px]",
} as const

export function GlassPill({
  variant = "default",
  size = "md",
  className,
  children,
  onClick,
  disabled,
}: GlassPillProps) {
  const classes = cn(
    variantMap[variant],
    sizeMap[size],
    "inline-flex items-center gap-1.5 font-medium whitespace-nowrap select-none",
    className
  )

  if (onClick) {
    return (
      <button type="button" className={classes} onClick={onClick} disabled={disabled}>
        {children}
      </button>
    )
  }

  return (
    <span className={classes}>
      {children}
    </span>
  )
}
