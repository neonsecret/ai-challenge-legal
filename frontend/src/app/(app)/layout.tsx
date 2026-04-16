"use client";

import {AppBackground} from "@/components/app-background";
import {BottomNav} from "@/components/bottom-nav";
import {ChatStateProvider} from "@/components/chat/chat-state";
import {StrictSidebarRail} from "@/components/chat/strict-sidebar-rail";
import {StrictMeshBlobs} from "@/components/landing/strict/strict-mesh-blobs";
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
                        {/* Mesh blobs — reuse landing page component */}
                        <StrictMeshBlobs />
                        {/* Glass pane */}
                        <div
                            style={{
                                flex: 1,
                                display: "flex",
                                position: "relative",
                                zIndex: 1,
                                borderRadius: isMobile ? 0 : 14,
                                background: "var(--strict-glass-bg)",
                                backdropFilter: "var(--strict-glass-blur)",
                                WebkitBackdropFilter: "var(--strict-glass-blur)",
                                border: isMobile ? "none" : "1px solid var(--strict-glass-border)",
                                boxShadow: isMobile ? "none" : "var(--strict-glass-shadow)",
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
                                    paddingBottom: isMobile ? "calc(env(safe-area-inset-bottom, 0px) + 72px)" : 0,
                                }}
                            >
                                {children}
                            </main>
                        </div>
                        {/* Mobile dark mode: bottom nav for page navigation */}
                        {isMobile && <BottomNav />}
                    </div>
                ) : (
                    /* Light mode: original layout with BottomNav */
                    <>
                        <main
                            className="flex-1 overflow-auto min-w-0"
                            style={{
                                position: "relative",
                                paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 80px)",
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
