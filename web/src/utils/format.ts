const priceFmt = new Intl.NumberFormat("ru-RU");
const numFmt = new Intl.NumberFormat("ru-RU");

export function formatPrice(n: number): string {
  return `${priceFmt.format(n)} ₸`;
}

export function formatNumber(n: number): string {
  return numFmt.format(n);
}

export function debounce<A extends unknown[]>(
  fn: (...args: A) => void,
  ms: number,
): (...args: A) => void {
  let t: ReturnType<typeof setTimeout> | null = null;
  return (...args: A) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
