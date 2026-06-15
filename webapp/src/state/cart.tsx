import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { skuToProduct, type Product } from "@/lib/catalog";

export interface CartLine {
  product: Product;
  qty: number;
}

interface CartCtx {
  lines: CartLine[];
  count: number;
  subtotal: number;
  addItem: (product: Product, qty?: number) => void;
  removeItem: (skuId: string) => void;
  clear: () => void;
}

const Ctx = createContext<CartCtx | null>(null);

// Cart starts with two demo items already in it (no cart backend in the prototype),
// and "Add to Cart" appends real items on top.
const SEED_SKUS = ["SKU-HEADPHONE-NC", "SKU-TSHIRT-CTN"];

function seedLines(): CartLine[] {
  return SEED_SKUS
    .map(skuToProduct)
    .filter((p): p is Product => Boolean(p))
    .map((product) => ({ product, qty: 1 }));
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(seedLines);

  const addItem = (product: Product, qty = 1) =>
    setLines((prev) => {
      const i = prev.findIndex((l) => l.product.sku_id === product.sku_id);
      if (i >= 0) {
        const next = [...prev];
        next[i] = { ...next[i], qty: next[i].qty + qty };
        return next;
      }
      return [...prev, { product, qty }];
    });

  const removeItem = (skuId: string) =>
    setLines((prev) => prev.filter((l) => l.product.sku_id !== skuId));

  const clear = () => setLines([]);

  const value = useMemo<CartCtx>(
    () => ({
      lines,
      addItem,
      removeItem,
      clear,
      count: lines.reduce((s, l) => s + l.qty, 0),
      subtotal: lines.reduce((s, l) => s + l.product.price * l.qty, 0),
    }),
    [lines],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart(): CartCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCart must be used within CartProvider");
  return v;
}
