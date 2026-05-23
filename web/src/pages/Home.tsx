import { ErrorRetryBanner } from "../components/ErrorRetryBanner";
import { ApiError } from "../api/client";
import {
  fetchXhsCachedNotes,
  fetchXhsNotePreview,
  listLatestNews,
  listMatchesForHome,
} from "../api/resources";
import type { Match, News, XhsCachedNoteRow, XhsNotePreview } from "../api/types";
import { XHS_DEMO_HREFS } from "../data/xhsDemoHrefs";
import { splitLabels } from "../utils/csvLabels";
import { sortHotMatches } from "../utils/matchSort";
import {
  Col,
  Empty,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import relativeTime from "dayjs/plugin/relativeTime";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useLocation } from "react-router-dom";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

const { Title, Paragraph, Text } = Typography;

type XhsPreviewState = { loading: boolean; data?: XhsNotePreview; error?: string };

function timeGreeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "夜深了，球迷 — 精彩回放同样值得";
  if (h < 11) return "早安 — 今日赛程与社区热点已就位";
  if (h < 14) return "午安 — 速递更新，随时刷新";
  if (h < 18) return "下午好 — 焦点赛场可能正在进行";
  return "晚上好 — 回顾今日资讯与比分";
}

function hueFromId(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i += 1) {
    h = (h * 31 + id.charCodeAt(i)) >>> 0;
  }
  return h % 360;
}

function statusTag(status: string) {
  const colors: Record<string, string> = {
    live: "magenta",
    scheduled: "processing",
    completed: "success",
    cancelled: "default",
  };
  const labels: Record<string, string> = {
    live: "LIVE",
    scheduled: "未赛",
    completed: "完赛",
    cancelled: "取消",
  };
  return (
    <Tag color={colors[status] ?? "default"} style={{ fontWeight: 700, fontSize: 11, margin: 0 }}>
      {labels[status] ?? status}
    </Tag>
  );
}

function relativeNewsTime(n: News): string {
  const t = n.published_at ?? n.created_at;
  return dayjs(t).fromNow();
}

function xhsExploreHrefToNoteId(href: string): string {
  return href.split("/").filter(Boolean).pop()?.toLowerCase() ?? "";
}

function xhsCachedRowToPreview(row: XhsCachedNoteRow): XhsNotePreview {
  let tags: string[] = [];
  if (row.tags_json) {
    try {
      const p = JSON.parse(row.tags_json) as unknown;
      if (Array.isArray(p)) {
        tags = p.filter((t): t is string => typeof t === "string");
      }
    } catch {
      /* ignore */
    }
  }
  const desc = row.body ?? null;
  return {
    title: row.title,
    image: row.image_url,
    description: desc,
    body: desc,
    tags,
  };
}

export function HomePage() {
  const location = useLocation();
  const [news, setNews] = useState<News[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [newsLoading, setNewsLoading] = useState(true);
  const [matchesLoading, setMatchesLoading] = useState(true);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [matchesError, setMatchesError] = useState<string | null>(null);
  const [newsRetryKey, setNewsRetryKey] = useState(0);
  const [matchesRetryKey, setMatchesRetryKey] = useState(0);
  const [xhsPreview, setXhsPreview] = useState<Record<string, XhsPreviewState>>({});
  const [xhsCoverBroken, setXhsCoverBroken] = useState<Record<string, boolean>>({});

  const greeting = useMemo(() => timeGreeting(), []);

  const localDiscoveryItems = useMemo(() => news.slice(0, 6), [news]);
  const wireItems = useMemo(() => news.slice(6), [news]);

  useEffect(() => {
    let cancelled = false;
    setNewsError(null);
    setNewsLoading(true);
    (async () => {
      try {
        const n = await listLatestNews(24);
        if (!cancelled) setNews(n.items);
      } catch (e) {
        if (!cancelled) setNewsError(e instanceof ApiError ? e.message : "新闻加载失败");
      } finally {
        if (!cancelled) setNewsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [newsRetryKey]);

  useEffect(() => {
    const st = location.state as { scrollTo?: string } | null | undefined;
    if (st?.scrollTo) {
      requestAnimationFrame(() => {
        document.getElementById(st.scrollTo)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      window.history.replaceState({}, document.title);
    }
  }, [location]);

  useEffect(() => {
    let cancelled = false;
    setMatchesError(null);
    setMatchesLoading(true);
    (async () => {
      try {
        const m = await listMatchesForHome(32);
        if (!cancelled) setMatches(sortHotMatches(m.items).slice(0, 10));
      } catch (e) {
        if (!cancelled) setMatchesError(e instanceof ApiError ? e.message : "比赛加载失败");
      } finally {
        if (!cancelled) setMatchesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [matchesRetryKey]);

  useEffect(() => {
    let cancelled = false;
    const initial: Record<string, XhsPreviewState> = Object.fromEntries(
      XHS_DEMO_HREFS.map((h) => [h, { loading: true }]),
    );
    setXhsPreview(initial);
    (async () => {
      let cacheByNoteId = new Map<string, XhsCachedNoteRow>();
      try {
        const { items } = await fetchXhsCachedNotes(120);
        for (const it of items) {
          const nid = it.note_id.toLowerCase();
          if (!cacheByNoteId.has(nid)) {
            cacheByNoteId.set(nid, it);
          }
        }
      } catch {
        /* 无缓存或接口失败时全部回退为实时抓取 */
      }
      const entries = await Promise.all(
        XHS_DEMO_HREFS.map(async (href) => {
          const nid = xhsExploreHrefToNoteId(href);
          const cached = nid ? cacheByNoteId.get(nid) : undefined;
          if (cached) {
            return [href, { loading: false as const, data: xhsCachedRowToPreview(cached) }] as const;
          }
          try {
            const data = await fetchXhsNotePreview(href);
            return [href, { loading: false as const, data }] as const;
          } catch (e) {
            const msg = e instanceof ApiError ? e.message : "抓取失败";
            return [href, { loading: false as const, error: msg }] as const;
          }
        }),
      );
      if (!cancelled) {
        setXhsPreview(Object.fromEntries(entries));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const scrollSection = { scrollMarginTop: 16 } as const;

  return (
    <>
      <section className="sport-hero">
        <div className="sport-hero-grid" aria-hidden />
        <div className="sport-hero-inner">
          <Tag
            style={{
              marginBottom: 12,
              border: "none",
              fontWeight: 600,
              letterSpacing: 1,
              background: "rgba(255,255,255,0.14)",
              color: "#f8fafc",
            }}
          >
            {greeting}
          </Tag>
          <Title level={1} className="sport-hero-title" style={{ color: "#f8fafc", margin: 0 }}>
            网球风向台
          </Title>
          <Paragraph
            style={{
              maxWidth: 560,
              fontSize: 16,
              marginTop: 12,
              marginBottom: 0,
              opacity: 0.92,
              color: "rgba(248,250,252,0.95)",
            }}
          >
            浏览社区热议、最新赛讯与近期赛程，一站掌握网球动态。
          </Paragraph>
        </div>
      </section>

      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "0 20px 56px" }}>
        <section id="section-discovery" style={{ marginBottom: 48, ...scrollSection }}>
          <div className="section-heading">
            <span className="section-kicker">社区感 · 信息流</span>
            <Title level={3} style={{ margin: "4px 0 4px" }}>
              球场热议
            </Title>
          </div>

          <div className="xhs-dual-feed">
            <div className="xhs-dual-feed-label">小红书</div>
            <Row gutter={[12, 12]}>
              {XHS_DEMO_HREFS.map((href, idx) => {
                const hue = hueFromId(href + String(idx));
                const st = xhsPreview[href];
                const loading = !st || st.loading;
                const data = st?.data;
                const err = st?.error;
                const title =
                  data?.title?.trim() ||
                  (loading ? "正在拉取笔记标题…" : err ? "抓取失败" : "小红书笔记");
                const desc =
                  data?.description?.trim().slice(0, 120) ||
                  (err ? err : loading ? "正在拉取简介…" : "");
                const tags = (data?.tags ?? []).slice(0, 5);
                const showImg = Boolean(data?.image && !xhsCoverBroken[href]);
                return (
                  <Col xs={12} sm={12} md={12} lg={12} key={href}>
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="xhs-card xhs-card-external"
                    >
                      <div
                        className="xhs-card-cover"
                        style={{
                          background: `linear-gradient(135deg, hsl(${hue}, 72%, 44%) 0%, hsl(${(hue + 48) % 360}, 58%, 26%) 100%)`,
                        }}
                      >
                        {showImg ? (
                          <img
                            className="xhs-card-cover-img"
                            src={data!.image!}
                            alt=""
                            referrerPolicy="no-referrer"
                            loading="lazy"
                            onError={() =>
                              setXhsCoverBroken((m) => ({
                                ...m,
                                [href]: true,
                              }))
                            }
                          />
                        ) : null}
                        {loading ? (
                          <div className="xhs-card-cover-loading">
                            <Spin size="small" />
                          </div>
                        ) : null}
                        <span className="xhs-card-cover-badge xhs-badge-xhs">小红书</span>
                        {!showImg && !loading ? (
                          <span className="xhs-card-cover-emoji" aria-hidden>
                            🎾
                          </span>
                        ) : null}
                      </div>
                      <div className="xhs-card-body">
                        <div className="xhs-card-title">{title}</div>
                        {desc ? <div className="xhs-card-desc">{desc}</div> : null}
                        <div className="xhs-card-meta">
                          <Space size={6} wrap>
                            {tags.map((t) => (
                              <span key={t} className="xhs-pill">
                                #{t}
                              </span>
                            ))}
                          </Space>
                          <span className="xhs-time">新窗口打开</span>
                        </div>
                      </div>
                    </a>
                  </Col>
                );
              })}
            </Row>

            <div className="xhs-dual-feed-label xhs-dual-feed-label-local" style={{ marginTop: 28 }}>
              站内资讯
            </div>

            {newsError ? (
              <ErrorRetryBanner
                message={newsError}
                loading={newsLoading}
                onRetry={() => setNewsRetryKey((k) => k + 1)}
              />
            ) : null}

            <Spin spinning={newsLoading} tip="加载站内热议…">
              {localDiscoveryItems.length === 0 && !newsLoading ? (
                <Empty description="暂无站内资讯" style={{ marginTop: 16 }} />
              ) : (
                <Row gutter={[12, 12]}>
                  {localDiscoveryItems.map((item) => {
                    const tags = splitLabels(item.tags).slice(0, 3);
                    const hue = hueFromId(item.id);
                    return (
                      <Col xs={12} sm={12} md={12} lg={12} key={item.id}>
                        <RouterLink to={`/news/${item.id}`} className="xhs-card" style={{ color: "inherit" }}>
                          <div
                            className="xhs-card-cover"
                            style={{
                              background: `linear-gradient(135deg, hsl(${hue}, 70%, 42%) 0%, hsl(${(hue + 40) % 360}, 55%, 28%) 100%)`,
                            }}
                          >
                            <span className="xhs-card-cover-badge">站内</span>
                            <span className="xhs-card-cover-emoji" aria-hidden>
                              🎾
                            </span>
                          </div>
                          <div className="xhs-card-body">
                            <div className="xhs-card-title">{item.title}</div>
                            {item.summary ? <div className="xhs-card-desc">{item.summary}</div> : null}
                            <div className="xhs-card-meta">
                              <Space size={6} wrap>
                                {tags.map((t) => (
                                  <span key={t} className="xhs-pill">
                                    #{t}
                                  </span>
                                ))}
                              </Space>
                              <span className="xhs-time">{relativeNewsTime(item)}</span>
                            </div>
                          </div>
                        </RouterLink>
                      </Col>
                    );
                  })}
                </Row>
              )}
            </Spin>
          </div>
        </section>

        <section id="section-wire" style={{ marginBottom: 48, ...scrollSection }}>
          <div className="section-heading">
            <span className="section-kicker wire-kicker">通讯社 · 赛讯</span>
            <Title level={3} style={{ margin: "4px 0 4px" }}>
              赛事前线
            </Title>
          </div>

          {newsError ? (
            <ErrorRetryBanner
              message={newsError}
              loading={newsLoading}
              onRetry={() => setNewsRetryKey((k) => k + 1)}
            />
          ) : null}

          <Spin spinning={newsLoading} tip="加载赛讯中…">
            {wireItems.length === 0 && !newsLoading ? (
              <Empty description={news.length > 0 ? "暂无更多资讯" : "暂无赛讯"} />
            ) : (
              <div className="wire-board">
                {wireItems.map((item) => {
                  const t = item.published_at ?? item.created_at;
                  const d = dayjs(t);
                  return (
                    <div key={item.id} className="wire-row">
                      <div className="wire-date">
                        <div className="wire-date-d">{d.format("DD")}</div>
                        <div className="wire-date-my">{d.format("YYYY.MM")}</div>
                        <div className="wire-date-hm">{d.format("HH:mm")}</div>
                      </div>
                      <div className="wire-divider" />
                      <div className="wire-main">
                        <RouterLink to={`/news/${item.id}`} className="wire-title">
                          {item.title}
                        </RouterLink>
                        {item.summary ? <div className="wire-summary">{item.summary}</div> : null}
                        <div className="wire-foot">
                          {item.source_url ? (
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="wire-link"
                            >
                              原文来源
                            </a>
                          ) : (
                            <span className="wire-muted">站内编辑</span>
                          )}
                          <span className="wire-muted">{relativeNewsTime(item)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Spin>
        </section>

        <section id="section-matches" style={{ ...scrollSection }}>
          <div className="section-heading">
            <span className="section-kicker match-kicker">巡回赛 · 日程板</span>
            <Title level={3} style={{ margin: "4px 0 4px" }}>
              巡回赛程
            </Title>
          </div>

          {matchesError ? (
            <ErrorRetryBanner
              message={matchesError}
              loading={matchesLoading}
              onRetry={() => setMatchesRetryKey((k) => k + 1)}
            />
          ) : null}

          <Spin spinning={matchesLoading} tip="加载赛程中…">
            {matches.length === 0 && !matchesLoading ? (
              <Empty description="暂无比赛" />
            ) : (
              <Row gutter={[16, 16]}>
                {matches.map((m) => (
                  <Col xs={24} sm={12} lg={8} key={m.id}>
                    <RouterLink
                      to={`/matches/${m.id}`}
                      style={{ color: "inherit", textDecoration: "none", display: "block" }}
                      className="match-board-card"
                    >
                      <div className="match-board-strip" />
                      <div className="match-board-inner">
                        <div className="match-board-head">
                          <Text strong ellipsis style={{ maxWidth: "70%" }}>
                            {m.tournament || m.name || "未命名赛事"}
                          </Text>
                          {statusTag(m.status)}
                        </div>
                        {m.event_round ? (
                          <Text type="secondary" className="match-board-round">
                            {m.event_round}
                          </Text>
                        ) : null}
                        {(m.home_side || m.away_side) && (
                          <div className="match-board-vs">
                            {[m.home_side, m.away_side].filter(Boolean).join("  vs  ")}
                          </div>
                        )}
                        {m.score ? <div className="match-board-score">{m.score}</div> : null}
                        <div className="match-board-foot">
                          {m.scheduled_at ? (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {dayjs(m.scheduled_at).format("YYYY-MM-DD HH:mm")}
                            </Text>
                          ) : null}
                          {m.venue ? (
                            <Text type="secondary" ellipsis style={{ fontSize: 12, maxWidth: "100%" }}>
                              {m.venue}
                            </Text>
                          ) : null}
                        </div>
                      </div>
                    </RouterLink>
                  </Col>
                ))}
              </Row>
            )}
          </Spin>
        </section>
      </div>
    </>
  );
}
