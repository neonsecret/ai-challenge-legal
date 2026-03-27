export type Jurisdiction = "difc" | "eu" | "uk" | "us" | "au" | "all";

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
};

export const JURISDICTION_ORDER: Jurisdiction[] = [
  "all",
  "difc",
  "eu",
  "uk",
  "us",
  "au",
];
