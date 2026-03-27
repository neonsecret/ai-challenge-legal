"use client";

import { useState, useEffect } from "react";
import type { Jurisdiction } from "./jurisdictions";

const STORAGE_KEY = "neolex_jurisdiction";
const DEFAULT_JURISDICTION: Jurisdiction = "all";
const CHANGE_EVENT = "neolex:jurisdiction-change";

export function useJurisdiction() {
  const [jurisdiction, setJurisdictionState] = useState<Jurisdiction>(
    DEFAULT_JURISDICTION
  );

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as Jurisdiction | null;
    if (stored) setJurisdictionState(stored);

    const handler = (e: Event) => {
      const detail = (e as CustomEvent<Jurisdiction>).detail;
      setJurisdictionState(detail);
    };
    window.addEventListener(CHANGE_EVENT, handler);
    return () => window.removeEventListener(CHANGE_EVENT, handler);
  }, []);

  const setJurisdiction = (j: Jurisdiction) => {
    localStorage.setItem(STORAGE_KEY, j);
    setJurisdictionState(j);
    window.dispatchEvent(
      new CustomEvent<Jurisdiction>(CHANGE_EVENT, { detail: j })
    );
  };

  return { jurisdiction, setJurisdiction };
}
