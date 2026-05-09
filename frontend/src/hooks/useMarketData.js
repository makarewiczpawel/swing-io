import { useState, useEffect, useCallback } from "react";
import { getCandles, getQuote, getMarketInfo, getIndicators, getRegime } from "../api/client";

/**
 * Hook do pobierania świec S&P 500.
 */
export function useCandles(interval = "1D", days = 365) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getCandles(interval, days);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [interval, days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

/**
 * Hook do pobierania bieżącej ceny.
 */
export function useQuote(refreshInterval = 60000) {
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchQuote = useCallback(async () => {
    try {
      const result = await getQuote();
      setQuote(result);
    } catch (err) {
      console.error("Quote fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQuote();
    const timer = setInterval(fetchQuote, refreshInterval);
    return () => clearInterval(timer);
  }, [fetchQuote, refreshInterval]);

  return { quote, loading, refetch: fetchQuote };
}

/**
 * Hook do pobierania info o rynku.
 */
export function useMarketInfo() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const result = await getMarketInfo();
        setInfo(result);
      } catch (err) {
        console.error("Market info error:", err);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

  return { info, loading };
}

export function useIndicators(interval = "1D", days = 365) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getIndicators(interval, days);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [interval, days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

export function useRegime(interval = "1D") {
  const [regime, setRegime] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const result = await getRegime(interval);
        setRegime(result);
      } catch (err) {
        console.error("Regime fetch error:", err);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [interval]);

  return { regime, loading };
}
