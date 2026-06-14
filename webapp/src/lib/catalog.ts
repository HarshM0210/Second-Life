// Local catalog + personas. SKUs/prices align with the Module 2 fixtures so the
// recommendation feed and shop are consistent. (In production this would come
// from a catalog service.)

export interface Product {
  sku_id: string;
  title: string;
  category: string;        // Module 1 category (return windows / weights)
  subcategory: string;     // Module 3 taxonomy key (risk scoring)
  brand: string;
  price: number;
  original_price: number;
  rating: number;
  reviews: number;
  renewed: boolean;
  health_score?: number;
  blurb: string;
  emoji: string;
}

export const CATALOG: Product[] = [
  {
    sku_id: "SKU-NIKE-RUN-8", title: "Nike Revolution Running Shoes (Size 8)",
    category: "Clothing & Footwear", subcategory: "Women's Shoes", brand: "Nike",
    price: 1999, original_price: 1999, rating: 4.3, reviews: 2140, renewed: false,
    blurb: "Lightweight, breathable mesh upper. Everyday road running.", emoji: "👟",
  },
  {
    sku_id: "SKU-NIKE-RUN-8R", title: "Nike Revolution Running Shoes (Size 8) — Renewed",
    category: "Clothing & Footwear", subcategory: "Women's Shoes", brand: "Nike",
    price: 1399, original_price: 1999, rating: 4.3, reviews: 2140, renewed: true,
    health_score: 94, blurb: "Certified Renewed. Excellent condition, 30% off.", emoji: "👟",
  },
  {
    sku_id: "SKU-BABYMON-1", title: "VTech Video Baby Monitor (Night Vision)",
    category: "Electronics", subcategory: "Earphones", brand: "VTech",
    price: 3500, original_price: 3500, rating: 4.6, reviews: 880, renewed: false,
    blurb: "1080p night vision, two-way audio, 300m range.", emoji: "📹",
  },
  {
    sku_id: "SKU-BABYMON-1R", title: "VTech Video Baby Monitor — Renewed",
    category: "Electronics", subcategory: "Earphones", brand: "VTech",
    price: 2100, original_price: 3500, rating: 4.6, reviews: 880, renewed: true,
    health_score: 88, blurb: "Certified Renewed. Very good condition, fully tested.", emoji: "📹",
  },
  {
    sku_id: "SKU-HEADPHONE-NC", title: "Sony Noise-Cancelling Headphones",
    category: "Electronics", subcategory: "Earphones", brand: "Sony",
    price: 8999, original_price: 8999, rating: 4.7, reviews: 5300, renewed: false,
    blurb: "Industry-leading ANC, 30h battery, wireless over-ear.", emoji: "🎧",
  },
  {
    sku_id: "SKU-HEADPHONE-NCR", title: "Sony Noise-Cancelling Headphones — Renewed",
    category: "Electronics", subcategory: "Earphones", brand: "Sony",
    price: 4500, original_price: 8999, rating: 4.7, reviews: 5300, renewed: true,
    health_score: 72, blurb: "Certified Renewed. Good condition, 50% off.", emoji: "🎧",
  },
  {
    sku_id: "SKU-COFFEE-PRESS", title: "Bialetti French Press Coffee Maker",
    category: "Other", subcategory: "Coffee Makers", brand: "Bialetti",
    price: 899, original_price: 899, rating: 4.4, reviews: 410, renewed: false,
    blurb: "Stainless steel, 1L, double-wall insulation.", emoji: "☕",
  },
  {
    sku_id: "SKU-YOGA-MAT", title: "Decathlon Non-Slip Yoga Mat",
    category: "Other", subcategory: "Yoga Mats", brand: "Decathlon",
    price: 599, original_price: 599, rating: 4.5, reviews: 1290, renewed: false,
    blurb: "Eco-friendly, 8mm cushioning, non-slip texture.", emoji: "🧘",
  },
];

export const skuToProduct = (sku: string): Product | undefined =>
  CATALOG.find((p) => p.sku_id === sku);

export interface Persona {
  customer_id: string;   // Module 1/3/4 id
  recommend_user_id: string; // Module 2 id
  name: string;
  role: "customer" | "seller";
  blurb: string;
}

export const PERSONAS: Persona[] = [
  { customer_id: "CUST-PRIYA", recommend_user_id: "u-priya", name: "Priya", role: "customer",
    blurb: "Returns ₹500 shoes — cost > value" },
  { customer_id: "CUST-RAHUL", recommend_user_id: "u-rahul", name: "Rahul", role: "customer",
    blurb: "Baby monitor → nearby parents" },
  { customer_id: "CUST-SELLER", recommend_user_id: "u-seller", name: "Small Seller", role: "seller",
    blurb: "200 returns/month, needs AI" },
];
