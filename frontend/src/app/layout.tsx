import type {Metadata} from "next";
import {Playfair_Display, Inter} from "next/font/google";
import "./globals.css";
import {ColorModeProvider} from "@/lib/color-mode";
import {TooltipProvider} from "@/components/ui/tooltip";
import {ToastProvider} from "@/components/ui/toast";
import {I18nProvider} from "@/lib/i18n";

const playfair = Playfair_Display({
    subsets: ["latin"],
    variable: "--font-heading",
    display: "swap",
});

const inter = Inter({
    subsets: ["latin"],
    variable: "--font-sans",
    display: "swap",
});

export const metadata: Metadata = {
    title: "Vitreon Legal — Your AI Legal Counsel",
    description: "AI-powered legal research and document analysis",
};

export default function RootLayout({
                                       children,
                                   }: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html
            lang="en"
            suppressHydrationWarning
            className={`${playfair.variable} ${inter.variable} h-full antialiased`}
        >
        <head>
            {/* Unified color-mode FOUC prevention — runs sync before paint.
                Priority: vitreon-color-mode > vitreon-design-version (migration) > theme (migration) > system */}
            <script dangerouslySetInnerHTML={{__html: `try{var cm=localStorage.getItem('vitreon-color-mode'),isDark=false;if(cm==='dark'){isDark=true}else if(cm==='light'){isDark=false}else if(cm==='system'||!cm){var dv=localStorage.getItem('vitreon-design-version');if(dv==='strict'){isDark=true;localStorage.setItem('vitreon-color-mode','dark')}else if(dv==='neon'){isDark=false;localStorage.setItem('vitreon-color-mode','light')}else{var th=localStorage.getItem('theme');if(th==='dark'){isDark=true;localStorage.setItem('vitreon-color-mode','dark')}else if(!th||th==='system'){isDark=window.matchMedia('(prefers-color-scheme: dark)').matches}}}if(isDark){document.documentElement.classList.add('dark');document.documentElement.classList.remove('light')}else{document.documentElement.classList.add('light');document.documentElement.classList.remove('dark')}}catch(e){document.documentElement.classList.add('light')}`}} />
        </head>
        <body className="h-full bg-background text-foreground">
        <ColorModeProvider>
            <I18nProvider>
                <TooltipProvider>
                    <ToastProvider>
                        {children}
                    </ToastProvider>
                </TooltipProvider>
            </I18nProvider>
        </ColorModeProvider>
        </body>
        </html>
    );
}
