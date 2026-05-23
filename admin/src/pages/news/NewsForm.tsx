import { App, Button, Card, DatePicker, Form, Input, Space } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { createNews, getNews, updateNews } from "../../api/resources";

export function NewsForm() {
  const { id } = useParams<{ id: string }>();
  const isNew = !id;
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(!isNew);

  useEffect(() => {
    if (isNew) return;
    let cancelled = false;
    (async () => {
      try {
        const row = await getNews(id!);
        if (cancelled) return;
        form.setFieldsValue({
          title: row.title,
          summary: row.summary ?? undefined,
          body: row.body ?? undefined,
          tags: row.tags ?? undefined,
          players: row.players ?? undefined,
          source_url: row.source_url ?? undefined,
          published_at: row.published_at ? dayjs(row.published_at) : undefined,
        });
      } catch (e) {
        message.error(e instanceof ApiError ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, isNew, form, message]);

  async function onFinish(values: {
    title: string;
    summary?: string;
    source_url?: string;
    published_at?: dayjs.Dayjs | null;
  }) {
    const payload = {
      title: values.title,
      summary: values.summary?.trim() || null,
      source_url: values.source_url?.trim() || null,
      published_at: values.published_at?.toISOString() ?? null,
    };
    try {
      if (isNew) {
        await createNews(payload);
        message.success("已创建");
      } else {
        await updateNews(id!, payload);
        message.success("已保存");
      }
      navigate("/news");
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  return (
    <Card title={isNew ? "新建新闻" : "编辑新闻"} loading={loading}>
      <Form form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 640 }}>
        <Form.Item name="title" label="标题" rules={[{ required: true, message: "请输入标题" }]}>
          <Input placeholder="标题" />
        </Form.Item>
        <Form.Item name="summary" label="摘要">
          <Input.TextArea rows={4} placeholder="列表摘要" />
        </Form.Item>
        <Form.Item name="body" label="正文">
          <Input.TextArea rows={10} placeholder="详情页正文（可选；不填时用户站用摘要作正文）" />
        </Form.Item>
        <Form.Item
          name="tags"
          label="标签"
          extra="逗号或中文逗号分隔，如：温网,红土"
        >
          <Input placeholder="温网, 红土" />
        </Form.Item>
        <Form.Item name="players" label="球员" extra="逗号或中文逗号分隔，如：费德勒,纳达尔">
          <Input placeholder="费德勒, 纳达尔" />
        </Form.Item>
        <Form.Item name="source_url" label="来源链接">
          <Input placeholder="https://..." />
        </Form.Item>
        <Form.Item name="published_at" label="发布时间">
          <DatePicker showTime style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
            <Link to="/news">返回列表</Link>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
}
