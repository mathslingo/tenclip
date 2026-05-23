import type { Match } from "../api/types";

function statusPriority(status: string): number {
  if (status === "live") return 3;
  if (status === "scheduled") return 2;
  if (status === "completed") return 1;
  return 0;
}

/** 直播优先，其次即将开赛，再为已结束；同组按时间合理排序 */
export function sortHotMatches(matches: Match[]): Match[] {
  const copy = [...matches];
  copy.sort((a, b) => {
    const pr = statusPriority(b.status) - statusPriority(a.status);
    if (pr !== 0) return pr;
    const ta = a.scheduled_at ? Date.parse(a.scheduled_at) : 0;
    const tb = b.scheduled_at ? Date.parse(b.scheduled_at) : 0;
    if (a.status === "scheduled" && b.status === "scheduled") return ta - tb;
    return tb - ta;
  });
  return copy;
}
