import {AppBackground} from "@/components/app-background";
import {BottomNav} from "@/components/bottom-nav";
import {ChatStateProvider} from "@/components/chat/chat-state";

export default function AppLayout({
                                      children,
                                  }: {
    children: React.ReactNode;
}) {
    return (
        <AppBackground>
            <ChatStateProvider>
                {/* Main content */}
                <main
                    className="flex-1 overflow-auto min-w-0"
                    style={{position: "relative", zIndex: 1, paddingBottom: "96px", overflowX: "hidden", maxWidth: "100vw"}}
                >
                    {children}
                </main>

                {/* Bottom nav pill */}
                <BottomNav/>
            </ChatStateProvider>
        </AppBackground>
    );
}
