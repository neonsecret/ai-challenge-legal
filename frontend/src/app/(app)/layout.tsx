"use client";

import {AppBackground} from "@/components/app-background";
import {BottomNav} from "@/components/bottom-nav";
import {ChatStateProvider} from "@/components/chat/chat-state";
import {MotionConfig} from "motion/react";
import {V3_MOTION_CONFIG} from "@/lib/v3-motion";
import {useColorMode} from "@/lib/color-mode";

export default function AppLayout({
                                      children,
                                  }: {
    children: React.ReactNode;
}) {
    const {isDark} = useColorMode();

    const inner = (
        <ChatStateProvider>
            {/* Main content */}
            <main
                className="flex-1 overflow-auto min-w-0"
                style={{
                    position: "relative",
                    paddingBottom: isDark ? 0 : "96px",
                    overflowX: "hidden",
                    maxWidth: "100vw",
                }}
            >
                {children}
            </main>

            {/* Bottom nav pill — hidden in dark mode (nav lives in sidebar rail) */}
            <BottomNav/>
        </ChatStateProvider>
    );

    return (
        <MotionConfig {...V3_MOTION_CONFIG}>
        <AppBackground>
            {isDark ? (
                /*
                 * Dark mode: AppBackground is transparent (no wrapper div),
                 * so we provide the structural flex shell here.
                 */
                <div
                    className="flex h-full w-full relative"
                    style={{overflowX: "hidden", background: "#000000"}}
                >
                    {inner}
                </div>
            ) : inner}
        </AppBackground>
        </MotionConfig>
    );
}
