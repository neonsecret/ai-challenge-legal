"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, FileText, Settings } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const navItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
        <div>
          <span className="text-xl font-bold tracking-tight text-[#d4af37]">
            NeoLex
          </span>
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
    </Sidebar>
  );
}
