export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface News {
  id: string;
  title: string;
  summary: string | null;
  body?: string | null;
  tags?: string | null;
  players?: string | null;
  source_url: string | null;
  published_at: string | null;
  created_at: string;
}

export interface Player {
  id: string;
  display_name: string;
  country_code: string | null;
  ranking_points: number | null;
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

export interface ListResponse<T> {
  items: T[];
  pagination: PaginationMeta;
}
