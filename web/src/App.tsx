import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Filters } from "@/components/Filters";
import { ProductGrid } from "@/components/ProductGrid";
import { Pagination } from "@/components/Pagination";
import { useProducts } from "@/hooks/useProducts";
import { api } from "@/utils/api";
import type { Category, ProductsQuery, Stats } from "@/types";
import styles from "@/App.module.css";

const DEFAULT_QUERY: ProductsQuery = {
  sort_by: "reviews",
  sort_dir: "desc",
  limit: 50,
  offset: 0,
};

export default function App() {
  const [query, setQuery] = useState<ProductsQuery>(DEFAULT_QUERY);
  const [categories, setCategories] = useState<Category[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const { data, loading, error } = useProducts(query);

  useEffect(() => {
    api.categories().then(setCategories).catch(console.error);
    api.stats().then(setStats).catch(console.error);
  }, []);

  const page = useMemo(
    () => Math.floor(query.offset / query.limit) + 1,
    [query.offset, query.limit],
  );
  const totalPages = useMemo(
    () => (data ? Math.max(1, Math.ceil(data.total / query.limit)) : 1),
    [data, query.limit],
  );

  const updateQuery = (patch: Partial<ProductsQuery>) => {
    setQuery((prev) => ({
      ...prev,
      ...patch,
      // whenever filters change, snap back to the first page
      offset: patch.offset != null ? patch.offset : 0,
    }));
  };

  return (
    <div className={styles.app}>
      <Header stats={stats} shown={data?.items.length ?? 0} total={data?.total ?? 0} />

      <main className={styles.main}>
        <Filters
          query={query}
          categories={categories}
          onChange={updateQuery}
        />

        {error && (
          <div className={styles.error}>
            Ошибка загрузки: {error.message}
          </div>
        )}

        <ProductGrid items={data?.items ?? []} loading={loading} />

        {data && data.total > query.limit && (
          <Pagination
            page={page}
            totalPages={totalPages}
            onPage={(p) => updateQuery({ offset: (p - 1) * query.limit })}
          />
        )}
      </main>

      <footer className={styles.footer}>
        Kaspi Analytics · Алматы
      </footer>
    </div>
  );
}
