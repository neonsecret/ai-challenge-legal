@AGENTS.md

# Frontend Rules

- Next.js 16 with App Router — read `node_modules/next/dist/docs/` before writing code
- Force-rebuild (`rm -rf .next && npm run build`) when UI changes aren't taking effect
- Use `eventsource-parser` for SSE streaming — never roll your own parser
- Never reorder [DOC-N] citation labels — see root CLAUDE.md rule 16
- Use design tokens from `src/lib/design-tokens.ts` — no magic numbers
- Use `motion/react` (not `framer-motion`) for animations
- Test E2E before deploying — see root CLAUDE.md rule 18
