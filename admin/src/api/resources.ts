import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type { ListResponse, Match, News, Player, Video } from "./types";

export function listNews(page: number, pageSize: number) {
  return apiGet<ListResponse<News>>("/news", { page, page_size: pageSize });
}

export function getNews(id: string) {
  return apiGet<News>(`/news/${id}`);
}

export function createNews(body: {
  title: string;
  summary?: string | null;
  body?: string | null;
  tags?: string | null;
  players?: string | null;
  source_url?: string | null;
  published_at?: string | null;
}) {
  return apiPost<News>("/news", body);
}

export function updateNews(
  id: string,
  body: Partial<{
    title: string;
    summary: string | null;
    body: string | null;
    tags: string | null;
    players: string | null;
    source_url: string | null;
    published_at: string | null;
  }>,
) {
  return apiPut<News>(`/news/${id}`, body);
}

export function deleteNews(id: string) {
  return apiDelete(`/news/${id}`);
}

export function listPlayers(page: number, pageSize: number) {
  return apiGet<ListResponse<Player>>("/players", { page, page_size: pageSize });
}

export function getPlayer(id: string) {
  return apiGet<Player>(`/players/${id}`);
}

export function createPlayer(body: {
  display_name: string;
  country_code?: string | null;
  ranking_points?: number | null;
}) {
  return apiPost<Player>("/players", body);
}

export function updatePlayer(
  id: string,
  body: Partial<{
    display_name: string;
    country_code: string | null;
    ranking_points: number | null;
  }>,
) {
  return apiPut<Player>(`/players/${id}`, body);
}

export function deletePlayer(id: string) {
  return apiDelete(`/players/${id}`);
}

export function listMatches(page: number, pageSize: number) {
  return apiGet<ListResponse<Match>>("/matches", { page, page_size: pageSize });
}

export function getMatch(id: string) {
  return apiGet<Match>(`/matches/${id}`);
}

export function createMatch(body: Record<string, unknown>) {
  return apiPost<Match>("/matches", body);
}

export function updateMatch(id: string, body: Record<string, unknown>) {
  return apiPut<Match>(`/matches/${id}`, body);
}

export function deleteMatch(id: string) {
  return apiDelete(`/matches/${id}`);
}

export function listVideos(page: number, pageSize: number) {
  return apiGet<ListResponse<Video>>("/videos", { page, page_size: pageSize });
}

export function getVideo(id: string) {
  return apiGet<Video>(`/videos/${id}`);
}

export function createVideo(body: Record<string, unknown>) {
  return apiPost<Video>("/videos", body);
}

export function updateVideo(id: string, body: Record<string, unknown>) {
  return apiPut<Video>(`/videos/${id}`, body);
}

export function deleteVideo(id: string) {
  return apiDelete(`/videos/${id}`);
}
