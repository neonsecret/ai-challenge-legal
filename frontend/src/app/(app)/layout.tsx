import {AppBackground} from "@/components/app-background";
import {BottomNav} from "@/components/bottom-nav";
import {ChatStateProvider} from "@/components/chat/chat-state";
import {MotionConfig} from "motion/react";
import {V3_MOTION_CONFIG} from "@/lib/v3-motion";

export default function AppLayout({
                                      children,
                                  }: {
    children: React.ReactNode;
}) {
    return (
        <MotionConfig {...V3_MOTION_CONFIG}>
        <AppBackground>
            <ChatStateProvider>
                {/* Main content */}
                <main
                    className="flex-1 overflow-auto min-w-0"
                    style={{position: "relative", paddingBottom: "96px", overflowX: "hidden", maxWidth: "100vw"}}
                >
                    {children}
                </main>

                {/* Bottom nav pill */}
                <BottomNav/>
            </ChatStateProvider>
        </AppBackground>
        </MotionConfig>
    );
}
