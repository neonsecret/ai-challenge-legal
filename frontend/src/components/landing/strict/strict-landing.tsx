"use client";

import { MotionConfig } from "motion/react";
import { StrictMeshBlobs } from "./strict-mesh-blobs";
import { StrictNav } from "./strict-nav";
import { StrictHero } from "./strict-hero";
import { StrictPreview } from "./strict-preview";
import { StrictHowItWorks } from "./strict-how-it-works";
import { StrictPricing } from "./strict-pricing";
import { StrictFooter } from "./strict-footer";

export function StrictLanding() {
  return (
    <MotionConfig reducedMotion="user">
      <div
        className="min-h-screen overflow-x-hidden"
        style={{ background: "var(--strict-bg-html)" }}
      >
        <StrictMeshBlobs />
        <StrictNav />
        <StrictHero />
        <StrictPreview />
        <StrictHowItWorks />
        <StrictPricing />
        <StrictFooter />
      </div>
    </MotionConfig>
  );
}
