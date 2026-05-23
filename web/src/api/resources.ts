import { apiGet, apiPost } from "./client";
import type {
  ListResponse,
  Match,
  News,
  Player,
  Video,
  XhsCachedNotesResponse,
  XhsNotePreview,
  XhsNotePreviewBatchResponse,
  XhsSearchNoteIdsResponse,
  XhsSearchPreviewsResponse,
} from "./types";

export function listLatestNews(pageSize = 12) {
  return apiGet<ListResponse<News>>("/news", { page: 1, page_size: pageSize });
}

/** 离线入库的小红书笔记缓存（按 `fetched_at` 倒序） */
export function fetchXhsCachedNotes(limit = 80) {
  return apiGet<XhsCachedNotesResponse>("/utils/xhs-cached-notes", { limit });
}

/** 服务端抓取小红书笔记页：meta / ld+json / 内嵌 JSON（无需 Cookie） */
export function fetchXhsNotePreview(url: string) {
  return apiGet<XhsNotePreview>("/utils/xhs-note-preview", { url });
}

/** 并行抓取多条笔记（`note_ids` 为 explore 路径最后一段，或与 `urls` 二选一混用） */
export function fetchXhsNotePreviewsBatch(body: { note_ids?: string[]; urls?: string[] }) {
  return apiPost<XhsNotePreviewBatchResponse>("/utils/xhs-note-previews", body);
}

/** 从搜索页 HTML 解析笔记 id（keyword 与官方 web 搜索参数一致） */
export function fetchXhsSearchNoteIds(params: {
  keyword?: string;
  search_url?: string;
  limit?: number;
}) {
  return apiGet<XhsSearchNoteIdsResponse>("/utils/xhs-search-note-ids", params);
}

/** 搜索 → 抠 id → 并行拉各条笔记 meta（与 `fetchXhsNotePreviewsBatch` 的 `items` 结构相同） */
export function fetchXhsSearchPreviews(params: {
  keyword?: string;
  search_url?: string;
  preview_limit?: number;
}) {
  return apiGet<XhsSearchPreviewsResponse>("/utils/xhs-search-previews", params);
}

export function listNewsPage(page: number, pageSize: number) {
  return apiGet<ListResponse<News>>("/news", { page, page_size: pageSize });
}

export function getNews(id: string) {
  return apiGet<News>(`/news/${encodeURIComponent(id)}`);
}

export function listMatchesForHome(pageSize = 24) {
  return apiGet<ListResponse<Match>>("/matches", { page: 1, page_size: pageSize });
}

export function getMatch(id: string) {
  return apiGet<Match>(`/matches/${encodeURIComponent(id)}`);
}

export function listVideosByMatch(matchId: string, pageSize = 50) {
  return apiGet<ListResponse<Video>>("/videos", {
    page: 1,
    page_size: pageSize,
    match_id: matchId,
  });
}

export function getPlayer(id: string) {
  return apiGet<Player>(`/players/${encodeURIComponent(id)}`);
}

export function listNewsForPlayer(playerId: string, page = 1, pageSize = 20) {
  return apiGet<ListResponse<News>>("/news", {
    page,
    page_size: pageSize,
    player_id: playerId,
  });
}

export function listMatchesForPlayer(playerId: string, page = 1, pageSize = 50) {
  return apiGet<ListResponse<Match>>("/matches", {
    page,
    page_size: pageSize,
    player_id: playerId,
  });
}
