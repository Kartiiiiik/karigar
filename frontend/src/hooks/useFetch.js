import { useCallback, useEffect, useState } from "react";
import api, { apiError } from "../lib/api";

/**
 * Minimal GET hook with loading/error state and a manual refresh.
 * `params` is a stable-serialised query object.
 */
export function useFetch(path, params) {
  // Passing params === null skips the request entirely (e.g. a staff-only
  // endpoint that a karigar must not call).
  const skip = params === null;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState("");
  const key = JSON.stringify(params ?? {});

  const refresh = useCallback(async () => {
    if (skip) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(path, { params: params ?? {} });
      setData(data);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, skip]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, error, refresh, setData };
}
