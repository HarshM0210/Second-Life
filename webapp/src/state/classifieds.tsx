import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { HealthCard, PriceQuote } from "@/types";

// A community Classifieds listing — an item a peer has put up for direct
// (peer-to-peer) resale. Each listing is graded by Module 1 (producing a
// Health Card) and priced by Module 5 (producing a PriceQuote), so the buyer
// sees an AI-certified condition and a fair, explainable asking price.
export interface Listing {
  id: string;
  title: string;
  emoji: string;
  category: string; // Module 1 category
  brand: string;
  seller: string; // persona display name
  original_price: number;
  age_months: number;
  // AI provenance (optional for seed/community items without a live grade).
  health_card?: HealthCard;
  quote?: PriceQuote;
  health_score?: number;
  condition?: string;
  ask_price: number; // gross asking price (₹)
  preview?: string; // data: URI of the seller's first photo, if any
  created_at: number;
  mine: boolean; // true if listed by the current session persona
}

interface ClassifiedsCtx {
  listings: Listing[];
  addListing: (l: Omit<Listing, "id" | "created_at">) => Listing;
}

const Ctx = createContext<ClassifiedsCtx | null>(null);

// Seed a couple of community listings so Browse is never empty during the demo.
// These mimic peers who already graded + priced their items via the same flow.
const SEED: Listing[] = [
  {
    id: "LST-SEED-1",
    title: "Sony WH-1000XM4 Headphones (gently used)",
    emoji: "🎧",
    category: "Electronics",
    brand: "Sony",
    seller: "Aarav",
    original_price: 8999,
    age_months: 14,
    health_score: 82,
    condition: "Good",
    ask_price: 4200,
    created_at: Date.now() - 1000 * 60 * 60 * 26,
    mine: false,
  },
  {
    id: "LST-SEED-2",
    title: "Levi's 511 Slim-Fit Jeans (worn twice)",
    emoji: "👖",
    category: "Clothing & Footwear",
    brand: "Levi's",
    seller: "Neha",
    original_price: 3499,
    age_months: 8,
    health_score: 88,
    condition: "Excellent",
    ask_price: 1450,
    created_at: Date.now() - 1000 * 60 * 60 * 5,
    mine: false,
  },
  {
    id: "LST-SEED-3",
    title: "Prestige Mixer Grinder (1 owner)",
    emoji: "🍶",
    category: "Other",
    brand: "Prestige",
    seller: "Vikram",
    original_price: 4500,
    age_months: 22,
    health_score: 71,
    condition: "Fair",
    ask_price: 1600,
    created_at: Date.now() - 1000 * 60 * 60 * 50,
    mine: false,
  },
];

export function ClassifiedsProvider({ children }: { children: ReactNode }) {
  const [listings, setListings] = useState<Listing[]>(SEED);

  const addListing = useCallback(
    (l: Omit<Listing, "id" | "created_at">): Listing => {
      const listing: Listing = {
        ...l,
        id: `LST-${Date.now().toString(36).toUpperCase()}`,
        created_at: Date.now(),
      };
      // Newest first.
      setListings((prev) => [listing, ...prev]);
      return listing;
    },
    [],
  );

  const value = useMemo<ClassifiedsCtx>(
    () => ({ listings, addListing }),
    [listings, addListing],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useClassifieds(): ClassifiedsCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useClassifieds must be used within ClassifiedsProvider");
  return v;
}
