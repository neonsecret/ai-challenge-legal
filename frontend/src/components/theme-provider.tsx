"use client";

// Re-exports ThemeProvider from the custom theme implementation.
// next-themes is intentionally NOT imported here — it caused a Turbopack SSR
// module-init bug (React null during build-time prerendering). See src/lib/theme.tsx.
export {ThemeProvider} from "@/lib/theme";
