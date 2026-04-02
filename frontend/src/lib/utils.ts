import {clsx, type ClassValue} from "clsx"
import {twMerge} from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

/** Coerce unknown value to string — prevents React #300 from non-string values leaking through API responses. */
export function toSafeString(x: unknown): string {
    return typeof x === "string" ? x : String(x ?? "")
}

/** Coerce unknown value to string, preserving null — for optional fields where null means "absent". */
export function toSafeStringOrNull(x: unknown): string | null {
    return x != null ? (typeof x === "string" ? x : String(x)) : null
}

/** Coerce unknown value to number with fallback — for page numbers and other numeric fields. */
export function toSafeNumber(x: unknown, fallback = 0): number {
    return typeof x === "number" ? x : Number(x ?? fallback)
}
