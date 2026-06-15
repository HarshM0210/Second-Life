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

  // --- More Electronics ---
  {
    sku_id: "SKU-SMARTWATCH-1", title: "boAt Xtend Smartwatch (1.69\" Display)",
    category: "Electronics", subcategory: "Wearables", brand: "boAt",
    price: 2499, original_price: 4999, rating: 4.1, reviews: 14200, renewed: false,
    blurb: "Bluetooth calling, 100+ sports modes, SpO2 & heart-rate.", emoji: "⌚",
  },
  {
    sku_id: "SKU-SMARTWATCH-1R", title: "boAt Xtend Smartwatch — Renewed",
    category: "Electronics", subcategory: "Wearables", brand: "boAt",
    price: 1499, original_price: 4999, rating: 4.1, reviews: 14200, renewed: true,
    health_score: 90, blurb: "Certified Renewed. Like-new, fully tested battery.", emoji: "⌚",
  },
  {
    sku_id: "SKU-POWERBANK-20K", title: "Mi 20000mAh Power Bank (Fast Charge)",
    category: "Electronics", subcategory: "Accessories", brand: "Mi",
    price: 1799, original_price: 2499, rating: 4.4, reviews: 9800, renewed: false,
    blurb: "18W fast charging, dual USB output, USB-C input.", emoji: "🔋",
  },
  {
    sku_id: "SKU-SPEAKER-BT", title: "JBL Go 3 Portable Bluetooth Speaker",
    category: "Electronics", subcategory: "Audio", brand: "JBL",
    price: 2299, original_price: 2999, rating: 4.6, reviews: 7600, renewed: false,
    blurb: "Bold JBL Pro sound, IP67 waterproof, 5h playtime.", emoji: "🔊",
  },
  {
    sku_id: "SKU-SPEAKER-BTR", title: "JBL Go 3 Bluetooth Speaker — Renewed",
    category: "Electronics", subcategory: "Audio", brand: "JBL",
    price: 1399, original_price: 2999, rating: 4.6, reviews: 7600, renewed: true,
    health_score: 85, blurb: "Certified Renewed. Very good condition, 53% off.", emoji: "🔊",
  },

  // --- More Clothing & Footwear ---
  {
    sku_id: "SKU-TSHIRT-CTN", title: "Allen Solly Cotton Crew-Neck T-Shirt",
    category: "Clothing & Footwear", subcategory: "Men's Clothing", brand: "Allen Solly",
    price: 699, original_price: 1299, rating: 4.2, reviews: 3400, renewed: false,
    blurb: "100% combed cotton, regular fit, breathable everyday tee.", emoji: "👕",
  },
  {
    sku_id: "SKU-JACKET-DENIM", title: "Levi's Trucker Denim Jacket",
    category: "Clothing & Footwear", subcategory: "Men's Clothing", brand: "Levi's",
    price: 3499, original_price: 4999, rating: 4.5, reviews: 1820, renewed: false,
    blurb: "Classic trucker fit, durable cotton denim, timeless style.", emoji: "🧥",
  },
  {
    sku_id: "SKU-JACKET-DENIMR", title: "Levi's Trucker Denim Jacket — Renewed",
    category: "Clothing & Footwear", subcategory: "Men's Clothing", brand: "Levi's",
    price: 1999, original_price: 4999, rating: 4.5, reviews: 1820, renewed: true,
    health_score: 87, blurb: "Certified Renewed. Excellent condition, inspected & cleaned.", emoji: "🧥",
  },
  {
    sku_id: "SKU-SNEAKER-AD", title: "Adidas Lite Racer Sneakers (Size 9)",
    category: "Clothing & Footwear", subcategory: "Men's Shoes", brand: "Adidas",
    price: 2799, original_price: 3999, rating: 4.3, reviews: 5100, renewed: false,
    blurb: "Cloudfoam comfort sockliner, lightweight everyday sneaker.", emoji: "👟",
  },
  {
    sku_id: "SKU-SANDAL-FF", title: "Crocs Classic Clogs (Unisex)",
    category: "Clothing & Footwear", subcategory: "Women's Shoes", brand: "Crocs",
    price: 1799, original_price: 2995, rating: 4.7, reviews: 12800, renewed: false,
    blurb: "Iconic lightweight clogs, ventilated, all-day comfort.", emoji: "🩴",
  },
  {
    sku_id: "SKU-KURTA-W", title: "Libas Cotton Anarkali Kurta",
    category: "Clothing & Footwear", subcategory: "Women's Clothing", brand: "Libas",
    price: 1199, original_price: 2499, rating: 4.3, reviews: 6700, renewed: false,
    blurb: "Flared cotton kurta with intricate print, festive-ready.", emoji: "👗",
  },
  {
    sku_id: "SKU-SHIRT-FORMAL", title: "Van Heusen Slim-Fit Formal Shirt",
    category: "Clothing & Footwear", subcategory: "Men's Clothing", brand: "Van Heusen",
    price: 1299, original_price: 2199, rating: 4.4, reviews: 4200, renewed: false,
    blurb: "Wrinkle-resistant cotton blend, slim fit, office-ready.", emoji: "👔",
  },
  {
    sku_id: "SKU-HOODIE-U", title: "H&M Relaxed-Fit Cotton Hoodie",
    category: "Clothing & Footwear", subcategory: "Men's Clothing", brand: "H&M",
    price: 1499, original_price: 1999, rating: 4.2, reviews: 5600, renewed: false,
    blurb: "Soft brushed-back sweat fabric, kangaroo pocket, unisex.", emoji: "🧥",
  },
  {
    sku_id: "SKU-JEANS-M", title: "Levi's 511 Slim-Fit Jeans",
    category: "Clothing & Footwear", subcategory: "Men's Clothing", brand: "Levi's",
    price: 2299, original_price: 3499, rating: 4.5, reviews: 8900, renewed: false,
    blurb: "Slim through hip and thigh, stretch denim, mid-rise.", emoji: "👖",
  },
  {
    sku_id: "SKU-HEELS-W", title: "Metro Block-Heel Sandals (Size 6)",
    category: "Clothing & Footwear", subcategory: "Women's Shoes", brand: "Metro",
    price: 1599, original_price: 2499, rating: 4.1, reviews: 1500, renewed: false,
    blurb: "Comfortable 2-inch block heel, cushioned footbed.", emoji: "👠",
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
];
