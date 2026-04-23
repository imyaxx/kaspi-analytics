import { useState, useEffect } from "react";
import type { Category, ProductsQuery, SortBy, SortDir } from "@/types";
import { debounce, formatNumber } from "@/utils/format";
import styles from "./Filters.module.css";

interface Props {
  query: ProductsQuery;
  categories: Category[];
  onChange: (patch: Partial<ProductsQuery>) => void;
}

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: "reviews", label: "По отзывам" },
  { value: "rating", label: "По рейтингу" },
  { value: "price", label: "По цене" },
  { value: "title", label: "По названию" },
];

const LIMIT_OPTIONS = [20, 50, 100, 200, 500, 1000];

export function Filters({ query, categories, onChange }: Props) {
  const [searchInput, setSearchInput] = useState(query.q ?? "");
  const [minPrice, setMinPrice] = useState(query.min_price?.toString() ?? "");
  const [maxPrice, setMaxPrice] = useState(query.max_price?.toString() ?? "");

  // Debounced text/number inputs so we don't refetch on every keystroke
  useEffect(() => {
    const apply = debounce(() => {
      onChange({
        q: searchInput.trim() || undefined,
        min_price: minPrice ? Number(minPrice) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
      });
    }, 300);
    apply();
  }, [searchInput, minPrice, maxPrice]); // eslint-disable-line

  return (
    <div className={styles.panel}>
      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Поиск</label>
          <input
            type="text"
            className={styles.input}
            placeholder="Название товара..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>

        <div className={styles.field}>
          <label className={styles.label}>Категория</label>
          <select
            className={styles.select}
            value={query.category ?? ""}
            onChange={(e) =>
              onChange({ category: e.target.value || undefined })
            }
          >
            <option value="">Все категории</option>
            {categories.map((c) => (
              <option key={c.code} value={c.code}>
                {c.title} ({formatNumber(c.product_count)})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Сортировка</label>
          <div className={styles.sortGroup}>
            <select
              className={styles.select}
              value={query.sort_by}
              onChange={(e) =>
                onChange({ sort_by: e.target.value as SortBy })
              }
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <button
              className={styles.dirBtn}
              onClick={() =>
                onChange({
                  sort_dir: (query.sort_dir === "asc"
                    ? "desc"
                    : "asc") as SortDir,
                })
              }
              title={
                query.sort_dir === "desc" ? "По убыванию" : "По возрастанию"
              }
            >
              {query.sort_dir === "desc" ? "↓" : "↑"}
            </button>
          </div>
        </div>

        <div className={styles.field}>
          <label className={styles.label}>Мин. рейтинг</label>
          <select
            className={styles.select}
            value={query.min_rating ?? ""}
            onChange={(e) =>
              onChange({
                min_rating: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          >
            <option value="">Любой</option>
            <option value="4.0">4.0+</option>
            <option value="4.3">4.3+</option>
            <option value="4.5">4.5+</option>
            <option value="4.7">4.7+</option>
            <option value="4.9">4.9+</option>
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label}>Мин. отзывов</label>
          <select
            className={styles.select}
            value={query.min_reviews ?? ""}
            onChange={(e) =>
              onChange({
                min_reviews: e.target.value
                  ? Number(e.target.value)
                  : undefined,
              })
            }
          >
            <option value="">Любое</option>
            <option value="100">100+</option>
            <option value="500">500+</option>
            <option value="1000">1000+</option>
            <option value="2000">2000+</option>
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label}>На странице</label>
          <select
            className={styles.select}
            value={query.limit}
            onChange={(e) => onChange({ limit: Number(e.target.value) })}
          >
            {LIMIT_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Цена от, ₸</label>
          <input
            type="number"
            className={styles.input}
            placeholder="0"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            min={0}
          />
        </div>

        <div className={styles.field}>
          <label className={styles.label}>Цена до, ₸</label>
          <input
            type="number"
            className={styles.input}
            placeholder="∞"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            min={0}
          />
        </div>

        <div className={styles.spacer} />

        <button
          className={styles.resetBtn}
          onClick={() => {
            setSearchInput("");
            setMinPrice("");
            setMaxPrice("");
            onChange({
              category: undefined,
              q: undefined,
              min_price: undefined,
              max_price: undefined,
              min_rating: undefined,
              min_reviews: undefined,
              sort_by: "reviews",
              sort_dir: "desc",
            });
          }}
        >
          Сбросить
        </button>
      </div>
    </div>
  );
}
