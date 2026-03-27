import { AppBackground } from "@/components/app-background";
import { BottomNav } from "@/components/bottom-nav";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppBackground>
      {/* Main content */}
      <main
        className="flex-1 overflow-auto min-w-0"
        style={{ position: "relative", zIndex: 1, paddingBottom: "96px" }}
      >
        {children}
      </main>

      {/* Bottom nav pill */}
      <BottomNav />
    </AppBackground>
  );
}
