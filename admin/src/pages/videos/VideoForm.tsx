import { App, Button, Card, Form, Input, InputNumber, Select, Space } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { createVideo, getVideo, updateVideo } from "../../api/resources";
import { useMatchOptions, usePlayerOptions } from "../../hooks/useEntityOptions";

export function VideoForm() {
  const { id } = useParams<{ id: string }>();
  const isNew = !id;
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(!isNew);
  const { options: playerOptions, loading: playersLoading } = usePlayerOptions();
  const { options: matchOptions, loading: matchesLoading } = useMatchOptions();

  useEffect(() => {
    if (isNew) return;
    let cancelled = false;
    (async () => {
      try {
        const row = await getVideo(id!);
        if (cancelled) return;
        form.setFieldsValue({
          title: row.title ?? undefined,
          storage_uri: row.storage_uri,
          duration_sec: row.duration_sec ?? undefined,
          match_id: row.match_id ?? undefined,
          primary_player_id: row.primary_player_id ?? undefined,
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
    title?: string;
    storage_uri: string;
    duration_sec?: number | null;
    match_id?: string;
    primary_player_id?: string;
  }) {
    const payload: Record<string, unknown> = {
      title: values.title?.trim() || null,
      storage_uri: values.storage_uri.trim(),
      duration_sec: values.duration_sec ?? null,
      match_id: values.match_id || null,
      primary_player_id: values.primary_player_id || null,
    };
    try {
      if (isNew) {
        await createVideo(payload);
        message.success("已创建");
      } else {
        await updateVideo(id!, payload);
        message.success("已保存");
      }
      navigate("/videos");
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  return (
    <Card title={isNew ? "新建视频" : "编辑视频"} loading={loading}>
      <Form form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 640 }}>
        <Form.Item name="title" label="标题">
          <Input placeholder="可选" />
        </Form.Item>
        <Form.Item
          name="storage_uri"
          label="存储 URI"
          rules={[{ required: true, message: "请输入存储地址" }]}
        >
          <Input placeholder="s3://... 或 https://..." />
        </Form.Item>
        <Form.Item name="duration_sec" label="时长（秒）">
          <InputNumber min={0} style={{ width: "100%" }} placeholder="可选" />
        </Form.Item>
        <Form.Item name="match_id" label="关联比赛">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            options={matchOptions}
            loading={matchesLoading}
            placeholder="可选"
          />
        </Form.Item>
        <Form.Item name="primary_player_id" label="主要球员">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            options={playerOptions}
            loading={playersLoading}
            placeholder="可选"
          />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
            <Link to="/videos">返回列表</Link>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
}
