"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Eye, EyeOff, Check, Moon, Sun, Monitor, ExternalLink } from "lucide-react";
import { useTheme } from "next-themes";

const APP_VERSION = "0.1.0";
const DEFAULT_API_URL = "http://localhost:8000";

type ThemeOption = "light" | "dark" | "system";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [apiKey, setApiKey] = useState("");
  const [backendUrl, setBackendUrl] = useState(DEFAULT_API_URL);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      setApiKey(localStorage.getItem("neolex_api_key") ?? "");
      setBackendUrl(
        localStorage.getItem("neolex_backend_url") ?? DEFAULT_API_URL
      );
    }
  }, []);

  const handleSave = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("neolex_api_key", apiKey.trim());
      localStorage.setItem("neolex_backend_url", backendUrl.trim() || DEFAULT_API_URL);
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const themeOptions: { value: ThemeOption; label: string; icon: React.ReactNode }[] = [
    { value: "light", label: "Light", icon: <Sun className="size-4" /> },
    { value: "dark", label: "Dark", icon: <Moon className="size-4" /> },
    { value: "system", label: "System", icon: <Monitor className="size-4" /> },
  ];

  return (
    <div className="flex flex-col gap-6 p-6 max-w-2xl mx-auto">
      {/* Page header */}
      <div>
        <p className="text-[11px] uppercase tracking-widest font-semibold mb-1" style={{ color: "rgba(201,168,76,0.7)" }}>
          Configuration
        </p>
        <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure your NeoLex connection and preferences
        </p>
      </div>

      {/* API Configuration */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle>API Configuration</CardTitle>
        </CardHeader>
        <CardContent className="pt-6 flex flex-col gap-5">
          {/* API Key */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="api-key"
              className="text-sm font-medium text-foreground"
            >
              API Key
            </label>
            <div className="relative">
              <Input
                id="api-key"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your NeoLex API key"
                className="pr-10 font-mono text-sm"
                autoComplete="off"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                aria-label={showKey ? "Hide API key" : "Show API key"}
              >
                {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Stored in browser localStorage. Never sent to third parties.
            </p>
          </div>

          {/* Backend URL */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="backend-url"
              className="text-sm font-medium text-foreground"
            >
              Backend URL
            </label>
            <Input
              id="backend-url"
              type="url"
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              NeoLex FastAPI server address. Use Tailscale URL for remote access.
            </p>
          </div>

          <Button onClick={handleSave} className="self-start gap-2">
            {saved ? (
              <>
                <Check className="size-4" />
                Saved
              </>
            ) : (
              "Save Changes"
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Theme</span>
            <div className="flex gap-2">
              {themeOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setTheme(opt.value)}
                  className={[
                    "flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                    theme === opt.value
                      ? "border-[#d4af37] bg-[#d4af37]/10 text-foreground"
                      : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground",
                  ].join(" ")}
                >
                  {opt.icon}
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* About */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle>About</CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Application</span>
              <span className="text-sm font-medium text-foreground">NeoLex</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Version</span>
              <Badge variant="outline" className="font-mono text-xs">
                v{APP_VERSION}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Backend</span>
              <a
                href={`${backendUrl || DEFAULT_API_URL}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-[#d4af37] hover:underline"
              >
                API Docs
                <ExternalLink className="size-3" />
              </a>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Tagline</span>
              <span className="text-sm text-muted-foreground italic">
                Your AI Legal Counsel
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
