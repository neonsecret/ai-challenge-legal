"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MessageSquare, FileText, Settings, LogOut } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";

const navItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [demoMode, setDemoMode] = useState(false);

  // Check demo mode from backend on mount
  useEffect(() => {
    const apiUrl =
      (typeof window !== "undefined"
        ? localStorage.getItem("neolex_backend_url")
        : null) ?? "http://localhost:8000";

    fetch(`${apiUrl}/api/v1/demo/config`)
      .then((r) => r.json())
      .then((data) => {
        if (data.demo_mode) setDemoMode(true);
      })
      .catch(() => {});
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("neolex_api_key");
    router.push("/");
  };

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold tracking-tight text-[#d4af37]">
              NeoLex
            </span>
            {demoMode && (
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 h-4 border-[#d4af37]/40 text-[#d4af37] bg-[#d4af37]/10"
              >
                Demo
              </Badge>
            )}
          </div>
          <p className="text-xs text-sidebar-foreground/60 mt-0.5">
            Your AI Legal Counsel
          </p>
        </div>
      </SidebarHeader>
      <SidebarContent className="pt-4">
        <SidebarMenu>
          {navItems.map(({ href, label, icon: Icon }) => (
            <SidebarMenuItem key={href}>
              <SidebarMenuButton
                isActive={pathname.startsWith(href)}
                render={
                  <Link href={href}>
                    <Icon className="size-4" />
                    <span>{label}</span>
                  </Link>
                }
              />
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border px-2 py-2">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full rounded-md px-3 py-2 text-sm text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          aria-label="Sign out"
        >
          <LogOut className="size-4" />
          <span>Sign out</span>
        </button>
      </SidebarFooter>
    </Sidebar>
  );
}
