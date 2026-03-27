"use client";

import { motion } from "motion/react";

interface FakePdfProps {
  showHighlights: boolean;
}

export function FakePdf({ showHighlights }: FakePdfProps) {
  return (
    <div className="relative h-full flex flex-col">
      {/* Page badge */}
      <div className="absolute top-3 right-3 z-10 bg-[#1B2B4B] text-white text-[10px] font-mono px-2 py-0.5 rounded">
        Page 7
      </div>

      {/* A4-ish white document card */}
      <div
        className="relative flex-1 bg-white rounded-xl shadow-lg overflow-hidden"
        style={{ fontFamily: "Georgia, serif" }}
      >
        <div className="p-5 h-full overflow-hidden text-[#1a1a1a]">
          {/* Document title */}
          <div className="text-center mb-4">
            <p className="text-[10px] font-bold tracking-widest text-[#333] uppercase mb-1">
              Supply Agreement
            </p>
            <div className="w-12 h-px bg-[#ccc] mx-auto" />
          </div>

          {/* Article header */}
          <p className="text-[9px] font-bold text-[#1B2B4B] mb-2 uppercase tracking-wide">
            Article 14 — Penalties and Liquidated Damages
          </p>

          {/* 14.1 */}
          <p className="text-[8px] leading-[1.55] text-[#333] mb-2">
            <span className="font-semibold">14.1</span> The Parties acknowledge
            that timely performance is of the essence of this Agreement, and any
            failure to deliver in accordance with the agreed schedule shall
            constitute a material default.
          </p>

          {/* 14.2 */}
          <p className="text-[8px] leading-[1.55] text-[#333] mb-2">
            <span className="font-semibold">14.2</span> Without prejudice to
            other remedies available at law or in equity, the Purchaser reserves
            the right to claim compensatory damages in excess of the liquidated
            amounts set forth herein.
          </p>

          {/* 14.3 — the highlighted section */}
          <div className="relative mb-2">
            <p className="text-[8px] leading-[1.55] text-[#333] relative z-10">
              <span className="font-semibold">14.3</span> In the event of late
              delivery, the Supplier shall pay to the Purchaser a penalty equal
              to zero point five percent (0.5%) of the total Contract Price for
              each day of delay, provided that the total{" "}
            </p>
            {/* Highlight line 1 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: showHighlights ? 1 : 0 }}
              transition={{ duration: 0.4, delay: 0 }}
              className="absolute inset-x-0 rounded-sm pointer-events-none"
              style={{
                top: "1.05em",
                height: "1.25em",
                backgroundColor: "rgba(201, 168, 76, 0.30)",
                zIndex: 0,
              }}
            />
            <p className="text-[8px] leading-[1.55] text-[#333] relative z-10">
              amount of penalties shall not exceed ten percent (10%) of the
              total Contract Price. Material breach of any obligation under this
              Agreement
            </p>
            {/* Highlight line 2 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: showHighlights ? 1 : 0 }}
              transition={{ duration: 0.4, delay: 0.15 }}
              className="absolute inset-x-0 rounded-sm pointer-events-none"
              style={{
                top: "2.3em",
                height: "1.25em",
                backgroundColor: "rgba(201, 168, 76, 0.30)",
                zIndex: 0,
              }}
            />
            <p className="text-[8px] leading-[1.55] text-[#333] relative z-10">
              shall require written notice specifying the nature of the breach
              and granting the defaulting Party a cure period of thirty (30)
              calendar
            </p>
            {/* Highlight line 3 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: showHighlights ? 1 : 0 }}
              transition={{ duration: 0.4, delay: 0.3 }}
              className="absolute inset-x-0 rounded-sm pointer-events-none"
              style={{
                top: "3.55em",
                height: "1.25em",
                backgroundColor: "rgba(201, 168, 76, 0.30)",
                zIndex: 0,
              }}
            />
            <p className="text-[8px] leading-[1.55] text-[#333] relative z-10">
              days from receipt of such notice.
            </p>
          </div>

          {/* 14.4 */}
          <p className="text-[8px] leading-[1.55] text-[#333]">
            <span className="font-semibold">14.4</span> The provisions of this
            Article shall survive termination or expiration of the Agreement and
            shall remain in full force until all obligations are discharged.
          </p>

          {/* Source badge */}
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: showHighlights ? 1 : 0, y: showHighlights ? 0 : 4 }}
            transition={{ duration: 0.3, delay: 0.5 }}
            className="absolute bottom-3 left-3 right-3 flex items-center gap-1.5 bg-[#1B2B4B]/90 backdrop-blur-sm rounded-md px-2.5 py-1.5"
          >
            <div className="size-1.5 rounded-full bg-[#C9A84C] shrink-0" />
            <span className="text-[9px] text-white font-mono">
              Article 14.3 · Supply Agreement · Page 7
            </span>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
