// Server component — force-dynamic skips static prerendering, which
// prevents a Next.js 16 Turbopack bug where ThemeProvider's React
// module is null during build-time prerender of this specific page.
export const dynamic = "force-dynamic";

import BillingSuccessClient from "./BillingSuccessClient";

export default function BillingSuccessPage() {
    return <BillingSuccessClient />;
}
