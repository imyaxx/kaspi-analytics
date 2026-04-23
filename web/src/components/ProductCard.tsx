import type { Product } from "@/types";
import { formatPrice, formatNumber } from "@/utils/format";
import styles from "./ProductCard.module.css";

interface Props {
  product: Product;
}

export function ProductCard({ product }: Props) {
  const hasDiscount =
    product.price_before_discount != null &&
    product.price_before_discount > product.price;

  return (
    <a
      className={styles.card}
      href={product.kaspi_url}
      target="_blank"
      rel="noopener noreferrer"
    >
      <div className={styles.imageWrap}>
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            className={styles.image}
            loading="lazy"
          />
        ) : (
          <div className={styles.imagePlaceholder}>📦</div>
        )}
        {hasDiscount && product.discount_pct != null && (
          <span className={styles.discountBadge}>
            −{product.discount_pct}%
          </span>
        )}
      </div>

      <div className={styles.body}>
        <h3 className={styles.title} title={product.title}>
          {product.title}
        </h3>

        {product.brand && product.brand !== "Без бренда" && (
          <div className={styles.brand}>{product.brand}</div>
        )}

        <div className={styles.priceRow}>
          <span className={styles.price}>{formatPrice(product.price)}</span>
          {hasDiscount && product.price_before_discount != null && (
            <span className={styles.priceOld}>
              {formatPrice(product.price_before_discount)}
            </span>
          )}
        </div>

        <div className={styles.meta}>
          <div className={styles.rating}>
            <span className={styles.star}>★</span>
            <span className={styles.ratingValue}>
              {product.rating.toFixed(1)}
            </span>
            <span className={styles.reviews}>
              {formatNumber(product.reviews)} отз.
            </span>
          </div>

          {product.stock > 0 ? (
            <span className={styles.inStock}>В наличии</span>
          ) : (
            <span className={styles.outOfStock}>Нет в наличии</span>
          )}
        </div>

        {product.category_title && (
          <div className={styles.category}>{product.category_title}</div>
        )}

        {product.best_merchant && (
          <div className={styles.merchant} title="Лучший продавец">
            🏪 {product.best_merchant}
          </div>
        )}
      </div>
    </a>
  );
}
