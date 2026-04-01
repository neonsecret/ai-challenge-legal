export type Jurisdiction = "difc" | "cz" | "eu" | "uk" | "us" | "au" | "all" | "custom";

export interface JurisdictionConfig {
    name: string;
    code: string;
    color: string;
    description: string;
}

export const JURISDICTIONS: Record<Jurisdiction, JurisdictionConfig> = {
    difc: {
        name: "DIFC",
        code: "AE",
        color: "#d4af37",
        description: "Dubai International Financial Centre",
    },
    cz: {
        name: "Czech Republic",
        code: "CZ",
        color: "#11457e",
        description: "Czech Legal Corpus",
    },
    eu: {
        name: "EU",
        code: "EU",
        color: "#003399",
        description: "European Union Law",
    },
    uk: {
        name: "UK",
        code: "GB",
        color: "#c8102e",
        description: "United Kingdom Law",
    },
    us: {
        name: "US",
        code: "US",
        color: "#3c3b6e",
        description: "United States Law",
    },
    au: {
        name: "AU",
        code: "AU",
        color: "#00008b",
        description: "Australian Law",
    },
    all: {
        name: "All Jurisdictions",
        code: "GL",
        color: "#d4af37",
        description: "All Jurisdictions",
    },
    custom: {
        name: "Custom",
        code: "\u2699",
        color: "#d4af37",
        description: "Custom corpus",
    },
};

export const JURISDICTION_ORDER: Jurisdiction[] = [
    "all",
    "difc",
    "cz",
    "eu",
    "uk",
    "us",
    "au",
];

/** Map jurisdiction to backend corpus name for the query API. */
export function jurisdictionToCorpus(j: Jurisdiction): string {
    switch (j) {
        case "cz":
            return "czech";
        case "difc":
            return "difc";
        case "uk":
            return "uk";
        case "au":
            return "au";
        case "custom":
            // Custom corpus name is stored separately in localStorage
            if (typeof window !== "undefined") {
                return localStorage.getItem("neolex_custom_corpus") || "difc";
            }
            return "difc";
        default:
            return "difc"; // Other jurisdictions default to DIFC for now
    }
}
