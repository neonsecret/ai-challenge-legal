"use client";

import dynamic from "next/dynamic";
import { MotionConfig } from "motion/react";
import { StrictMeshBlobs } from "./strict-mesh-blobs";
import { StrictNav } from "./strict-nav";
import { StrictHero } from "./strict-hero";

// Below-fold sections — not SSR'd, loaded client-side after LCP fires.
// StrictMeshBlobs, StrictNav, StrictHero are above-fold and stay eager.
const StrictPreview = dynamic(() => import("./strict-preview").then(m => ({ default: m.StrictPreview })), { ssr: false });
const StrictDocumentDraftingShowcase = dynamic(() => import("./strict-document-drafting-showcase").then(m => ({ default: m.StrictDocumentDraftingShowcase })), { ssr: false });
const StrictHowItWorks = dynamic(() => import("./strict-how-it-works").then(m => ({ default: m.StrictHowItWorks })), { ssr: false });
const StrictPricing = dynamic(() => import("./strict-pricing").then(m => ({ default: m.StrictPricing })), { ssr: false });
const StrictFooter = dynamic(() => import("./strict-footer").then(m => ({ default: m.StrictFooter })), { ssr: false });

export function StrictLanding() {
  return (
    <MotionConfig reducedMotion="user">
      <div
        className="min-h-screen overflow-x-hidden"
        style={{
          background: "var(--strict-bg-html)",
          maxWidth: "100vw",
        }}
      >
        <StrictMeshBlobs />
        <StrictNav />
        <StrictHero />
        <StrictPreview />
        <StrictDocumentDraftingShowcase />
        <StrictHowItWorks />
        <StrictPricing />
        <StrictFooter />
      </div>
    </MotionConfig>
  );
}
