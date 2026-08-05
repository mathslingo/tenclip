import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

const BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

/** 与登录页写入 localStorage 时使用的 key 保持一致 */
export const TOKEN_STORAGE_KEY = "tenclip_access_token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const http = axios.create({
  baseURL: BASE,
  headers: {
    Accept: "application/json",
  },
});

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ error?: { message?: string; detail?: unknown } }>) => {
    const res = error.response;
    if (res?.data && typeof res.data === "object" && "error" in res.data) {
      const payload = res.data.error;
      const msg = payload?.message ?? error.message;
      throw new ApiError(res.status, msg, payload?.detail);
    }
    if (res) {
      throw new ApiError(res.status, error.message);
    }
    throw error;
  },
);

export async function apiGet<T>(path: string, query?: Record<string, string | number | undefined>) {
  const { data } = await http.get<T>(path, { params: query });
  return data;
}

export async function apiPost<T>(path: string, body?: unknown) {
  const { data } = await http.post<T>(path, body);
  return data;
}
