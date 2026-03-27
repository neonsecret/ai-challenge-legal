import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex h-full w-full">
        <AppSidebar />
        <div className="flex flex-col flex-1 min-w-0">
          {/* Mobile top bar — only visible when sidebar is hidden */}
          <div
            className="md:hidden flex items-center gap-3 h-12 px-4 shrink-0"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
          >
            <SidebarTrigger />
            <span className="font-heading text-sm font-bold text-[#C9A84C]">
              NeoLex
            </span>
          </div>
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
