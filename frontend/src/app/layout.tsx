import type {Metadata} from "next";
import {Playfair_Display, Inter} from "next/font/google";
import "./globals.css";
import {ThemeProvider} from "@/components/theme-provider";
import {DesignVersionProvider} from "@/lib/design-version";
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
            {/* Inline theme script — runs sync before body paint to prevent FOUC.
                Mirrors next-themes behaviour (storageKey='theme', attribute='class',
                defaultTheme='system') now that ThemeProvider uses ssr:false. */}
            <script dangerouslySetInnerHTML={{__html: `try{var t=localStorage.getItem('theme');if(t==='dark'||(t==='system'||!t)&&window.matchMedia('(prefers-color-scheme: dark)').matches){document.documentElement.classList.add('dark')}}catch(e){}`}} />
            {/* Inline design-version script — prevents FOUC for saved design version.
                Must run before paint so CSS tokens load correctly on first frame. */}
            <script dangerouslySetInnerHTML={{__html: `try{var dv=localStorage.getItem('vitreon-design-version');if(dv==='v2'){document.documentElement.classList.add('design-v2')}else if(dv==='v3'){document.documentElement.classList.add('design-v3')}}catch(e){}`}} />
        </head>
        <body className="h-full bg-background text-foreground">
        <ThemeProvider>
            <DesignVersionProvider>
                <I18nProvider>
                    <TooltipProvider>
                        <ToastProvider>
                            {children}
                        </ToastProvider>
                    </TooltipProvider>
                </I18nProvider>
            </DesignVersionProvider>
        </ThemeProvider>
        </body>
        </html>
    );
}
