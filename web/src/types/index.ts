export type SortBy = "reviews" | "rating" | "price" | "title";
export type SortDir = "asc" | "desc";

export interface Category {
  code: string;
  title: string;
  product_count: number;
}

export interface Product {
  id: string;
  title: string;
  brand: string | null;
  category_code: string | null;
  category_title: string | null;
  price: number;
  price_before_discount: number | null;
  discount_pct: number | null;
  rating: number;
  reviews: number;
  stock: number;
  best_merchant: string | null;
  image_url: string | null;
  kaspi_url: string;
  shop_link: string | null;
}

export interface ProductsResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface Stats {
  total_products: number;
  total_categories: number;
  last_run: {
    started_at: string;
    finished_at: string | null;
    products_saved: number;
    products_seen: number;
  } | null;
}

export interface ProductsQuery {
  category?: string;
  q?: string;
  min_price?: number;
  max_price?: number;
  min_rating?: number;
  min_reviews?: number;
  sort_by: SortBy;
  sort_dir: SortDir;
  limit: number;
  offset: number;
}
