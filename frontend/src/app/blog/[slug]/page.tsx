import {notFound} from "next/navigation";

/*
 * Dynamic blog route — acts as a catch-all for blog slugs that don't have
 * a dedicated static page. In Next.js App Router, static segments
 * (e.g. blog/arlc-2026-results/page.tsx) take priority over dynamic
 * segments, so actual posts are served from their own TSX files.
 *
 * This route exists to:
 * 1. Return proper 404s for invalid blog slugs
 * 2. Provide infrastructure for future CMS/dynamic posts
 */
export default function BlogPostPage() {
    notFound();
}
