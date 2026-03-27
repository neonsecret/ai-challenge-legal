import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex h-dvh w-full overflow-hidden">
        <AppSidebar />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          {/* Mobile topbar — visible only on small screens */}
          <header
            className="flex md:hidden items-center gap-3 px-4 h-14 shrink-0 border-b"
            style={{
              background: "oklch(0.14 0.04 240)",
              borderColor: "rgba(255,255,255,0.08)",
            }}
          >
            <SidebarTrigger
              className="text-white/50 hover:text-white/80 hover:bg-white/10 rounded-md p-1.5 transition-colors"
              aria-label="Toggle navigation"
            />
            <span
              className="font-heading text-lg font-bold tracking-tight"
              style={{ color: "#C9A84C" }}
            >
              NeoLex
            </span>
          </header>
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
