import {
  Breadcrumb,
  Card,
  Descriptions,
  Empty,
  List,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ErrorRetryBanner } from "../components/ErrorRetryBanner";
import { LoadErrorResult } from "../components/LoadErrorResult";
import { ApiError } from "../api/client";
import { getPlayer, listMatchesForPlayer, listNewsForPlayer } from "../api/resources";
import type { Match, News, Player } from "../api/types";

const { Title, Paragraph, Text } = Typography;

function statusColor(status: string): string {
  if (status === "live") return "red";
  if (status === "scheduled") return "blue";
  if (status === "completed") return "green";
  return "default";
}

export function PlayerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const [player, setPlayer] = useState<Player | null>(null);
  const [news, setNews] = useState<News[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(false);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [matchesError, setMatchesError] = useState<string | null>(null);
  const [playerRetryKey, setPlayerRetryKey] = useState(0);
  const [newsRetryKey, setNewsRetryKey] = useState(0);
  const [matchesRetryKey, setMatchesRetryKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setError(null);
    setLoading(true);
    setPlayer(null);
    (async () => {
      try {
        const p = await getPlayer(id);
        if (!cancelled) setPlayer(p);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "加载失败");
          setPlayer(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, playerRetryKey]);

  useEffect(() => {
    if (!id || !player) return;
    let cancelled = false;
    setNewsError(null);
    setNewsLoading(true);
    (async () => {
      try {
        const res = await listNewsForPlayer(id, 1, 20);
        if (!cancelled) setNews(res.items);
      } catch (e) {
        if (!cancelled) {
          setNewsError(e instanceof ApiError ? e.message : "相关新闻加载失败");
          setNews([]);
        }
      } finally {
        if (!cancelled) setNewsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, player, newsRetryKey]);

  useEffect(() => {
    if (!id || !player) return;
    let cancelled = false;
    setMatchesError(null);
    setMatchesLoading(true);
    (async () => {
      try {
        const res = await listMatchesForPlayer(id, 1, 50);
        if (!cancelled) setMatches(res.items);
      } catch (e) {
        if (!cancelled) {
          setMatchesError(e instanceof ApiError ? e.message : "比赛记录加载失败");
          setMatches([]);
        }
      } finally {
        if (!cancelled) setMatchesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, player, matchesRetryKey]);

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin size="large" tip="加载球员信息…" />
      </div>
    );
  }

  if (error || !player) {
    return (
      <LoadErrorResult
        subTitle={error ?? "未找到该球员"}
        onRetry={() => {
          setLoading(true);
          setPlayerRetryKey((k) => k + 1);
        }}
        retryLoading={loading}
      />
    );
  }

  return (
    <div style={{ maxWidth: 880, margin: "0 auto", padding: "24px 16px 48px" }}>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <Link to="/" state={location.state}>
                首页
              </Link>
            ),
          },
          { title: "球员" },
        ]}
      />

      <Card style={{ marginBottom: 24 }}>
        <Title level={2} style={{ marginTop: 0 }}>
          {player.display_name}
        </Title>
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small" style={{ marginTop: 16 }}>
          <Descriptions.Item label="国家/地区">{player.country_code ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="排名积分">
            {player.ranking_points != null ? String(player.ranking_points) : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="建档时间">
            {dayjs(player.created_at).format("YYYY-MM-DD HH:mm")}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Title level={4}>相关新闻</Title>
      <Paragraph type="secondary" style={{ marginTop: -8, marginBottom: 12 }}>
        匹配规则：标题、摘要、正文、标签或「相关球员」字段中包含该球员姓名（{player.display_name}）。
      </Paragraph>
      {newsError ? (
        <ErrorRetryBanner
          message={newsError}
          loading={newsLoading}
          onRetry={() => setNewsRetryKey((k) => k + 1)}
        />
      ) : null}
      <Spin spinning={newsLoading} tip="加载相关新闻…">
        {!newsError && news.length === 0 && !newsLoading ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无相关新闻" />
        ) : !newsError ? (
          <List
            dataSource={news}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={<Link to={`/news/${item.id}`}>{item.title}</Link>}
                  description={
                    <Text type="secondary" ellipsis>
                      {(item.summary || "").slice(0, 160)}
                      {(item.summary?.length ?? 0) > 160 ? "…" : ""}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        ) : null}
      </Spin>

      <Title level={4} style={{ marginTop: 32 }}>
        历史比赛
      </Title>
      {matchesError ? (
        <ErrorRetryBanner
          message={matchesError}
          loading={matchesLoading}
          onRetry={() => setMatchesRetryKey((k) => k + 1)}
        />
      ) : null}
      <Spin spinning={matchesLoading} tip="加载比赛记录…">
        {!matchesError && matches.length === 0 && !matchesLoading ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无比赛记录" />
        ) : !matchesError ? (
          <List
            dataSource={matches}
            renderItem={(m) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space wrap>
                      <Link to={`/matches/${m.id}`}>
                        {m.tournament || m.name || "比赛"}
                        {m.event_round ? ` · ${m.event_round}` : ""}
                      </Link>
                      <Tag color={statusColor(m.status)}>{m.status}</Tag>
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      {(m.home_side || m.away_side) && (
                        <Text type="secondary">
                          {[m.home_side, m.away_side].filter(Boolean).join(" vs ")}
                        </Text>
                      )}
                      {m.score ? <Text strong>比分 {m.score}</Text> : null}
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {m.scheduled_at ? dayjs(m.scheduled_at).format("YYYY-MM-DD HH:mm") : "时间待定"}
                        {m.venue ? ` · ${m.venue}` : ""}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        ) : null}
      </Spin>
    </div>
  );
}
