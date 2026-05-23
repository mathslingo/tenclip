export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface News {
  id: string;
  title: string;
  summary: string | null;
  /** 独立正文；缺省时详情页用 summary 展示 */
  body?: string | null;
  /** 逗号 / 中文逗号分隔 */
  tags?: string | null;
  /** 逗号 / 中文逗号分隔的球员名 */
  players?: string | null;
  source_url: string | null;
  published_at: string | null;
  created_at: string;
}

export interface Match {
  id: string;
  name: string | null;
  tournament: string | null;
  event_round: string | null;
  home_side: string | null;
  away_side: string | null;
  player1_id: string | null;
  player2_id: string | null;
  score: string | null;
  venue: string | null;
  scheduled_at: string | null;
  status: string;
  created_at: string;
}

export interface Video {
  id: string;
  title: string | null;
  storage_uri: string;
  duration_sec: number | null;
  match_id: string | null;
  primary_player_id: string | null;
  created_at: string;
}

export interface Player {
  id: string;
  display_name: string;
  country_code: string | null;
  ranking_points: number | null;
  created_at: string;
}

export interface ListResponse<T> {
  items: T[];
  pagination: PaginationMeta;
}

/** Core API `GET /utils/xhs-note-preview` */
export interface XhsNotePreview {
  title: string | null;
  image: string | null;
  description: string | null;
  /** 与 description 同源（服务端离线入库时用作文本正文占位） */
  body?: string | null;
  tags: string[];
}

/** Core API `POST /utils/xhs-note-previews` 单条结果（成功无 `error`，失败带 `error`） */
export interface XhsNotePreviewBatchItem extends XhsNotePreview {
  url: string;
  error?: string;
}

export interface XhsNotePreviewBatchResponse {
  items: XhsNotePreviewBatchItem[];
}

/** `GET /utils/xhs-search-note-ids` */
export interface XhsSearchNoteIdsResponse {
  note_ids: string[];
  search_url: string;
}

/** `GET /utils/xhs-cached-notes` 单条缓存 */
export interface XhsCachedNoteRow {
  note_id: string;
  explore_url: string;
  title: string | null;
  body: string | null;
  image_url: string | null;
  tags_json: string | null;
  fetched_at: string | null;
}

export interface XhsCachedNotesResponse {
  items: XhsCachedNoteRow[];
}
