import { useMemo } from "react";
import styles from "./Pagination.module.css";

interface Props {
  page: number;
  totalPages: number;
  onPage: (p: number) => void;
}

/** Produce page numbers with ellipses: 1 … 4 5 [6] 7 8 … 42 */
function pageRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const result: (number | "…")[] = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  if (start > 2) result.push("…");
  for (let i = start; i <= end; i++) result.push(i);
  if (end < total - 1) result.push("…");
  result.push(total);
  return result;
}

export function Pagination({ page, totalPages, onPage }: Props) {
  const pages = useMemo(() => pageRange(page, totalPages), [page, totalPages]);

  return (
    <nav className={styles.nav} aria-label="Пагинация">
      <button
        className={styles.btn}
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
      >
        ←
      </button>

      {pages.map((p, i) =>
        p === "…" ? (
          <span key={`e-${i}`} className={styles.ellipsis}>
            …
          </span>
        ) : (
          <button
            key={p}
            className={`${styles.btn} ${p === page ? styles.active : ""}`}
            onClick={() => onPage(p)}
          >
            {p}
          </button>
        ),
      )}

      <button
        className={styles.btn}
        onClick={() => onPage(page + 1)}
        disabled={page >= totalPages}
      >
        →
      </button>
    </nav>
  );
}
