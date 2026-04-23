import type {
  Category,
  ProductsQuery,
  ProductsResponse,
  Stats,
} from "@/types";

const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

function toParams(q: ProductsQuery): string {
  const p = new URLSearchParams();
  p.set("sort_by", q.sort_by);
  p.set("sort_dir", q.sort_dir);
  p.set("limit", String(q.limit));
  p.set("offset", String(q.offset));
  if (q.category) p.set("category", q.category);
  if (q.q) p.set("q", q.q);
  if (q.min_price != null) p.set("min_price", String(q.min_price));
  if (q.max_price != null) p.set("max_price", String(q.max_price));
  if (q.min_rating != null) p.set("min_rating", String(q.min_rating));
  if (q.min_reviews != null) p.set("min_reviews", String(q.min_reviews));
  return p.toString();
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  categories: () => request<Category[]>("/api/categories"),
  products: (q: ProductsQuery) =>
    request<ProductsResponse>(`/api/products?${toParams(q)}`),
};
