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
  theme,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ErrorRetryBanner } from "../components/ErrorRetryBanner";
import { LoadErrorResult } from "../components/LoadErrorResult";
import { ApiError } from "../api/client";
import { getMatch, getPlayer, listVideosByMatch } from "../api/resources";
import type { Match, Player, Video } from "../api/types";

const { Title, Paragraph, Text } = Typography;

function statusColor(status: string): string {
  if (status === "live") return "red";
  if (status === "scheduled") return "blue";
  if (status === "completed") return "green";
  return "default";
}

function formatDuration(sec: number | null): string {
  if (sec == null || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`;
}

export function MatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const { token } = theme.useToken();
  const [match, setMatch] = useState<Match | null>(null);
  const [p1, setP1] = useState<Player | null>(null);
  const [p2, setP2] = useState<Player | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [videosLoading, setVideosLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [videosError, setVideosError] = useState<string | null>(null);
  const [matchRetryKey, setMatchRetryKey] = useState(0);
  const [videosRetryKey, setVideosRetryKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setError(null);
    setLoading(true);
    setMatch(null);
    setP1(null);
    setP2(null);
    (async () => {
      try {
        const m = await getMatch(id);
        if (cancelled) return;
        setMatch(m);
        const loads: Promise<void>[] = [];
        if (m.player1_id) {
          loads.push(
            getPlayer(m.player1_id)
              .then((p) => {
                if (!cancelled) setP1(p);
              })
              .catch(() => {
                if (!cancelled) setP1(null);
              }),
          );
        }
        if (m.player2_id) {
          loads.push(
            getPlayer(m.player2_id)
              .then((p) => {
                if (!cancelled) setP2(p);
              })
              .catch(() => {
                if (!cancelled) setP2(null);
              }),
          );
        }
        await Promise.all(loads);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "加载失败");
          setMatch(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, matchRetryKey]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setVideosError(null);
    setVideosLoading(true);
    (async () => {
      try {
        const res = await listVideosByMatch(id, 50);
        if (!cancelled) setVideos(res.items);
      } catch (e) {
        if (!cancelled) {
          setVideosError(e instanceof ApiError ? e.message : "视频列表加载失败");
          setVideos([]);
        }
      } finally {
        if (!cancelled) setVideosLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, videosRetryKey]);

  const side1 =
    match?.home_side?.trim() ||
    p1?.display_name ||
    (match?.player1_id ? `球员 ${match.player1_id.slice(0, 8)}…` : "待定");
  const side2 =
    match?.away_side?.trim() ||
    p2?.display_name ||
    (match?.player2_id ? `球员 ${match.player2_id.slice(0, 8)}…` : "待定");

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin size="large" tip="加载比赛信息…" />
      </div>
    );
  }

  if (error || !match) {
    return (
      <LoadErrorResult
        subTitle={error ?? "未找到该比赛"}
        onRetry={() => {
          setLoading(true);
          setMatchRetryKey((k) => k + 1);
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
          { title: "比赛详情" },
        ]}
      />

      <Card style={{ marginBottom: 24 }}>
        <Space align="center" wrap style={{ marginBottom: 16 }}>
          <Title level={2} style={{ margin: 0 }}>
            {match.name || match.tournament || "比赛详情"}
          </Title>
          <Tag color={statusColor(match.status)}>{match.status}</Tag>
        </Space>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            padding: "24px 0",
            borderRadius: token.borderRadiusLG,
            background: token.colorFillAlter,
            marginBottom: 24,
          }}
        >
          {match.player1_id ? (
            <Link to={`/players/${match.player1_id}`} style={{ fontSize: 20, fontWeight: 600, color: "inherit" }}>
              {side1}
            </Link>
          ) : (
            <Text style={{ fontSize: 20, fontWeight: 600 }}>{side1}</Text>
          )}
          <Text type="secondary" style={{ fontSize: 18 }}>
            VS
          </Text>
          {match.player2_id ? (
            <Link to={`/players/${match.player2_id}`} style={{ fontSize: 20, fontWeight: 600, color: "inherit" }}>
              {side2}
            </Link>
          ) : (
            <Text style={{ fontSize: 20, fontWeight: 600 }}>{side2}</Text>
          )}
        </div>

        {match.score ? (
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <Text type="secondary" style={{ fontSize: 14 }}>
              比分
            </Text>
            <Title level={2} style={{ margin: "8px 0 0" }}>
              {match.score}
            </Title>
          </div>
        ) : (
          <Paragraph type="secondary" style={{ textAlign: "center" }}>
            暂无比分
          </Paragraph>
        )}

        <Title level={4}>赛事信息</Title>
        <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="赛事">{match.tournament ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="轮次">{match.event_round ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="场地">{match.venue ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="开赛时间">
            {match.scheduled_at ? dayjs(match.scheduled_at).format("YYYY-MM-DD HH:mm") : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="主场标识">{match.home_side ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="客场标识">{match.away_side ?? "—"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Title level={4}>视频集锦</Title>
      {videosError ? (
        <ErrorRetryBanner
          message={videosError}
          loading={videosLoading}
          onRetry={() => setVideosRetryKey((k) => k + 1)}
        />
      ) : null}
      <Spin spinning={videosLoading} tip="加载视频列表…">
        {!videosError && videos.length === 0 && !videosLoading ? (
          <Empty description="本场暂无关联视频" />
        ) : !videosError ? (
          <List
            dataSource={videos}
            renderItem={(v) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    v.storage_uri.startsWith("http://") || v.storage_uri.startsWith("https://") ? (
                      <Typography.Link href={v.storage_uri} target="_blank" rel="noreferrer">
                        {v.title || "观看视频"}
                      </Typography.Link>
                    ) : (
                      <Text>{v.title || "视频"}</Text>
                    )
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      <Text type="secondary" ellipsis style={{ maxWidth: "100%" }}>
                        {v.storage_uri}
                      </Text>
                      <Text type="secondary">时长 {formatDuration(v.duration_sec)}</Text>
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
