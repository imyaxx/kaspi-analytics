import type { Product } from "@/types";
import { ProductCard } from "./ProductCard";
import styles from "./ProductGrid.module.css";

interface Props {
  items: Product[];
  loading: boolean;
}

export function ProductGrid({ items, loading }: Props) {
  if (loading && items.length === 0) {
    return (
      <div className={styles.state}>
        <div className={styles.spinner} />
        <div>Загрузка...</div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className={styles.state}>
        <div className={styles.empty}>🔍</div>
        <div>По выбранным фильтрам ничего не найдено</div>
      </div>
    );
  }

  return (
    <div className={styles.grid} data-loading={loading}>
      {items.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  );
}
