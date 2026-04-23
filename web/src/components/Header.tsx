import type { Stats } from "@/types";
import { formatNumber } from "@/utils/format";
import styles from "./Header.module.css";

interface Props {
  stats: Stats | null;
  shown: number;
  total: number;
}

export function Header({ stats, shown, total }: Props) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brand}>
          <span className={styles.dot} />
          <h1 className={styles.title}>Kaspi Analytics</h1>
        </div>

        <div className={styles.stats}>
          <Stat label="Товаров в базе" value={stats?.total_products ?? 0} />
          <Stat label="Категорий" value={stats?.total_categories ?? 0} />
          <Stat
            label="Показано"
            value={shown}
            sub={total > shown ? `из ${formatNumber(total)}` : undefined}
          />
        </div>
      </div>
    </header>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: number;
  sub?: string;
}) {
  return (
    <div className={styles.stat}>
      <div className={styles.statLabel}>{label}</div>
      <div className={styles.statValue}>
        {formatNumber(value)}
        {sub && <span className={styles.statSub}> {sub}</span>}
      </div>
    </div>
  );
}
