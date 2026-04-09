"use client";

import { STRICT_MESH } from "@/lib/strict-tokens";

const BLOBS = [
  { top: "-5%", left: "-5%", width: 400, height: 400, bg: "rgba(201,168,76,0.04)", delay: 0 },
  { bottom: "-10%", right: "-5%", width: 350, height: 350, bg: "rgba(100,130,200,0.03)", delay: -3 },
  { top: "40%", left: "55%", width: 300, height: 300, bg: "rgba(201,168,76,0.025)", delay: -6 },
] as const;

export function StrictMeshBlobs() {
  return (
    <>
      {BLOBS.map((blob, i) => (
        <div
          key={i}
          className="fixed rounded-full pointer-events-none"
          style={{
            top: "top" in blob ? blob.top : undefined,
            bottom: "bottom" in blob ? blob.bottom : undefined,
            left: "left" in blob ? blob.left : undefined,
            right: "right" in blob ? blob.right : undefined,
            width: blob.width,
            height: blob.height,
            background: blob.bg,
            filter: "blur(80px)",
            animation: `strict-drift ${STRICT_MESH.driftDuration}s ease-in-out infinite`,
            animationDelay: `${blob.delay}s`,
            willChange: "transform",
          }}
        />
      ))}
    </>
  );
}
