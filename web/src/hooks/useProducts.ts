import { useEffect, useRef, useState } from "react";
import { api } from "@/utils/api";
import type { ProductsQuery, ProductsResponse } from "@/types";

export function useProducts(query: ProductsQuery) {
  const [data, setData] = useState<ProductsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const reqId = useRef(0);

  useEffect(() => {
    const myId = ++reqId.current;
    setLoading(true);
    setError(null);

    api
      .products(query)
      .then((res) => {
        if (myId === reqId.current) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (myId === reqId.current) {
          setError(err);
          setLoading(false);
        }
      });
  }, [
    query.category,
    query.q,
    query.min_price,
    query.max_price,
    query.min_rating,
    query.min_reviews,
    query.sort_by,
    query.sort_dir,
    query.limit,
    query.offset,
  ]);

  return { data, loading, error };
}
