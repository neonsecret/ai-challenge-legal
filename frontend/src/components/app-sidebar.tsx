"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MessageSquare, FileText, Settings, LogOut, Clock } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";

const navItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

const RECENT_QUERIES_KEY = "neolex_recent_queries";
const MAX_RECENT = 5;

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [demoMode, setDemoMode] = useState(false);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);

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

    // Load recent queries from localStorage
    try {
      const stored = localStorage.getItem(RECENT_QUERIES_KEY);
      if (stored) {
        setRecentQueries(JSON.parse(stored).slice(0, MAX_RECENT));
      }
    } catch {
      // ignore
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("neolex_api_key");
    router.push("/");
  };

  return (
    <Sidebar>
      {/* Header — NeoLex brand in Playfair */}
      <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-heading text-xl font-bold tracking-tight text-[#C9A84C]">
              NeoLex
            </span>
            {demoMode && (
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 h-4 border-[#C9A84C]/40 text-[#C9A84C] bg-[#C9A84C]/10"
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
        {/* Main navigation */}
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

        {/* Recent queries */}
        {recentQueries.length > 0 && (
          <SidebarGroup className="mt-6">
            <SidebarGroupLabel className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-sidebar-foreground/50 px-3 mb-1">
              <Clock className="size-3" />
              Recent Queries
            </SidebarGroupLabel>
            <div className="px-2 flex flex-col gap-0.5">
              {recentQueries.map((q, i) => (
                <button
                  key={i}
                  onClick={() => router.push("/chat")}
                  className="w-full text-left text-xs text-sidebar-foreground/70 hover:text-sidebar-foreground px-3 py-2 rounded-md hover:bg-sidebar-accent transition-colors truncate"
                  title={q}
                >
                  {q}
                </button>
              ))}
            </div>
          </SidebarGroup>
        )}

        {/* Placeholder when no recent queries */}
        {recentQueries.length === 0 && (
          <SidebarGroup className="mt-6">
            <SidebarGroupLabel className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-sidebar-foreground/50 px-3 mb-1">
              <Clock className="size-3" />
              Recent Queries
            </SidebarGroupLabel>
            <p className="px-5 text-xs text-sidebar-foreground/40 italic">
              Your queries will appear here
            </p>
          </SidebarGroup>
        )}
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
