import {
  Breadcrumb,
  Card,
  Divider,
  Empty,
  List,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ErrorRetryBanner } from "../components/ErrorRetryBanner";
import { LoadErrorResult } from "../components/LoadErrorResult";
import { ApiError } from "../api/client";
import { getNews, listNewsPage } from "../api/resources";
import type { News } from "../api/types";
import { splitLabels } from "../utils/csvLabels";

const { Title, Paragraph, Text } = Typography;

function relatedScore(a: News, current: News, currentTags: Set<string>): number {
  let s = 0;
  const ta = splitLabels(a.tags);
  for (const t of ta) {
    if (currentTags.has(t)) s += 3;
  }
  const pa = splitLabels(a.players);
  const cp = splitLabels(current.players);
  const cpSet = new Set(cp);
  for (const p of pa) {
    if (cpSet.has(p)) s += 2;
  }
  if (
    a.title &&
    current.title &&
    (a.title.includes(current.title.slice(0, 4)) || current.title.includes(a.title.slice(0, 4)))
  ) {
    s += 1;
  }
  return s;
}

export function NewsDetailPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const [detail, setDetail] = useState<News | null>(null);
  const [related, setRelated] = useState<News[]>([]);
  const [loading, setLoading] = useState(true);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relatedError, setRelatedError] = useState<string | null>(null);
  const [detailRetryKey, setDetailRetryKey] = useState(0);
  const [relatedRetryKey, setRelatedRetryKey] = useState(0);

  const publishedLabel = useMemo(() => {
    if (!detail) return "";
    const t = detail.published_at ?? detail.created_at;
    return dayjs(t).format("YYYY-MM-DD HH:mm");
  }, [detail]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setError(null);
    setLoading(true);
    setDetail(null);
    (async () => {
      try {
        const row = await getNews(id);
        if (!cancelled) setDetail(row);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "加载失败");
          setDetail(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, detailRetryKey]);

  useEffect(() => {
    if (!id || !detail) return;
    let cancelled = false;
    setRelatedError(null);
    setRelatedLoading(true);
    (async () => {
      try {
        const res = await listNewsPage(1, 40);
        if (cancelled) return;
        const currentTags = new Set(splitLabels(detail.tags));
        const others = res.items.filter((n) => n.id !== id);
        const sorted = [...others].sort(
          (a, b) => relatedScore(b, detail, currentTags) - relatedScore(a, detail, currentTags),
        );
        setRelated(sorted.slice(0, 8));
      } catch (e) {
        if (!cancelled) {
          setRelatedError(e instanceof ApiError ? e.message : "相关新闻加载失败");
          setRelated([]);
        }
      } finally {
        if (!cancelled) setRelatedLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, detail, relatedRetryKey]);

  const bodyText = detail?.body?.trim() || detail?.summary?.trim() || "";
  const bodyFromSummary = !detail?.body?.trim() && !!detail?.summary?.trim();
  const tagItems = splitLabels(detail?.tags);
  const playerItems = splitLabels(detail?.players);

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin size="large" tip="加载新闻详情…" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <LoadErrorResult
        subTitle={error ?? "未找到该新闻"}
        onRetry={() => {
          setLoading(true);
          setDetailRetryKey((k) => k + 1);
        }}
        retryLoading={loading}
      />
    );
  }

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "24px 16px 48px" }}>
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
          { title: "新闻详情" },
        ]}
      />

      <Card style={{ marginBottom: 24 }}>
        <Title level={2} style={{ marginTop: 0 }}>
          {detail.title}
        </Title>
        <Space wrap size={[8, 8]} style={{ marginBottom: 16 }}>
          <Text type="secondary">发布时间：{publishedLabel}</Text>
          {detail.source_url ? (
            <Typography.Link href={detail.source_url} target="_blank" rel="noreferrer">
              查看原文链接
            </Typography.Link>
          ) : null}
        </Space>

        {(tagItems.length > 0 || playerItems.length > 0) && (
          <>
            <Divider orientation="left" plain>
              标签与球员
            </Divider>
            <Space wrap size={[8, 8]}>
              {playerItems.map((p) => (
                <Tag key={`p-${p}`} color="blue">
                  {p}
                </Tag>
              ))}
              {tagItems.map((t) => (
                <Tag key={`t-${t}`}>{t}</Tag>
              ))}
            </Space>
          </>
        )}

        <Divider orientation="left" plain>
          正文
        </Divider>
        {bodyText ? (
          <>
            {bodyFromSummary ? (
              <Paragraph type="secondary" style={{ marginBottom: 12 }}>
                未配置独立正文字段，以下为摘要内容。
              </Paragraph>
            ) : null}
            <Paragraph style={{ whiteSpace: "pre-wrap", fontSize: 16, lineHeight: 1.75 }}>{bodyText}</Paragraph>
          </>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无正文（可在后台填写正文或摘要）" />
        )}
      </Card>

      <Title level={4}>相关新闻</Title>
      {relatedError ? (
        <ErrorRetryBanner
          message={relatedError}
          loading={relatedLoading}
          onRetry={() => setRelatedRetryKey((k) => k + 1)}
        />
      ) : null}
      <Spin spinning={relatedLoading} tip="加载相关推荐…">
        {!relatedError && related.length === 0 && !relatedLoading ? (
          <Empty description="暂无更多新闻" />
        ) : !relatedError ? (
          <List
            dataSource={related}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={<Link to={`/news/${item.id}`}>{item.title}</Link>}
                  description={
                    <Text type="secondary" ellipsis style={{ maxWidth: "100%" }}>
                      {(item.summary || "").slice(0, 120)}
                      {(item.summary?.length ?? 0) > 120 ? "…" : ""}
                    </Text>
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
