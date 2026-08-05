import { useEffect, useState } from "react";
import { listMatches, listPlayers } from "../api/resources";
import type { DefaultOptionType } from "antd/es/select";

export function usePlayerOptions() {
  const [options, setOptions] = useState<DefaultOptionType[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listPlayers(1, 500);
        if (cancelled) return;
        setOptions(
          res.items.map((p) => ({
            value: p.id,
            label: `${p.display_name}${p.country_code ? ` (${p.country_code})` : ""}`,
          })),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return { options, loading };
}

export function useMatchOptions() {
  const [options, setOptions] = useState<DefaultOptionType[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listMatches(1, 500);
        if (cancelled) return;
        setOptions(
          res.items.map((m) => ({
            value: m.id,
            label:
              m.name ||
              [m.tournament, m.event_round, m.score].filter(Boolean).join(" · ") ||
              m.id.slice(0, 8),
          })),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return { options, loading };
}
