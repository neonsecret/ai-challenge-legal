"use client";

import {AppBackground} from "@/components/app-background";
import {BottomNav} from "@/components/bottom-nav";
import {ChatStateProvider} from "@/components/chat/chat-state";
import {StrictSidebarRail} from "@/components/chat/strict-sidebar-rail";
import {MotionConfig} from "motion/react";
import {V3_MOTION_CONFIG} from "@/lib/v3-motion";
import {useColorMode} from "@/lib/color-mode";
import {useIsMobile} from "@/hooks/use-mobile";
import {usePathname} from "next/navigation";

export default function AppLayout({
                                      children,
                                  }: {
    children: React.ReactNode;
}) {
    const {isDark} = useColorMode();
    const isMobile = useIsMobile();
    const pathname = usePathname();
    const isChat = pathname.startsWith("/chat");

    return (
        <MotionConfig {...V3_MOTION_CONFIG}>
        <AppBackground>
            <ChatStateProvider>
                {isDark ? (
                    /* Dark mode: glass pane + sidebar rail shell for ALL pages */
                    <div
                        style={{
                            position: "fixed",
                            inset: 0,
                            display: "flex",
                            padding: isMobile ? 0 : 12,
                            background: "var(--strict-page-bg)",
                            overflow: "hidden",
                        }}
                    >
                        {/* Glass pane */}
                        <div
                            style={{
                                flex: 1,
                                display: "flex",
                                borderRadius: isMobile ? 0 : 14,
                                background: "rgba(255,255,255, 0.02)",
                                backdropFilter: "blur(24px)",
                                WebkitBackdropFilter: "blur(24px)",
                                border: isMobile ? "none" : "1px solid rgba(201,168,76, 0.06)",
                                boxShadow: isMobile ? "none" : "0 16px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.025)",
                                overflow: "hidden",
                                minWidth: 0,
                            }}
                        >
                            {/* Sidebar rail — desktop only */}
                            {!isMobile && (
                                <StrictSidebarRail />
                            )}

                            {/* Page content */}
                            <main
                                className="flex-1 overflow-auto min-w-0"
                                style={{
                                    position: "relative",
                                    overflowX: "hidden",
                                    display: "flex",
                                    flexDirection: "column",
                                }}
                            >
                                {children}
                            </main>
                        </div>
                    </div>
                ) : (
                    /* Light mode: original layout with BottomNav */
                    <>
                        <main
                            className="flex-1 overflow-auto min-w-0"
                            style={{
                                position: "relative",
                                paddingBottom: "96px",
                                overflowX: "hidden",
                                maxWidth: "100vw",
                            }}
                        >
                            {children}
                        </main>
                        <BottomNav/>
                    </>
                )}
            </ChatStateProvider>
        </AppBackground>
        </MotionConfig>
    );
}
