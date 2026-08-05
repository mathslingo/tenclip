import { App, Button, Card, DatePicker, Form, Input, Select, Space } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { createMatch, getMatch, updateMatch } from "../../api/resources";
import { usePlayerOptions } from "../../hooks/useEntityOptions";

const statusOptions = [
  { value: "scheduled", label: "scheduled" },
  { value: "live", label: "live" },
  { value: "completed", label: "completed" },
  { value: "cancelled", label: "cancelled" },
];

export function MatchForm() {
  const { id } = useParams<{ id: string }>();
  const isNew = !id;
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(!isNew);
  const { options: playerOptions, loading: playersLoading } = usePlayerOptions();

  useEffect(() => {
    if (isNew) return;
    let cancelled = false;
    (async () => {
      try {
        const row = await getMatch(id!);
        if (cancelled) return;
        form.setFieldsValue({
          name: row.name ?? undefined,
          tournament: row.tournament ?? undefined,
          event_round: row.event_round ?? undefined,
          home_side: row.home_side ?? undefined,
          away_side: row.away_side ?? undefined,
          player1_id: row.player1_id ?? undefined,
          player2_id: row.player2_id ?? undefined,
          score: row.score ?? undefined,
          venue: row.venue ?? undefined,
          scheduled_at: row.scheduled_at ? dayjs(row.scheduled_at) : undefined,
          status: row.status,
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

  async function onFinish(values: Record<string, unknown>) {
    const payload: Record<string, unknown> = {
      name: (values.name as string)?.trim() || null,
      tournament: (values.tournament as string)?.trim() || null,
      event_round: (values.event_round as string)?.trim() || null,
      home_side: (values.home_side as string)?.trim() || null,
      away_side: (values.away_side as string)?.trim() || null,
      player1_id: values.player1_id || null,
      player2_id: values.player2_id || null,
      score: (values.score as string)?.trim() || null,
      venue: (values.venue as string)?.trim() || null,
      scheduled_at: (values.scheduled_at as dayjs.Dayjs | null)?.toISOString() ?? null,
      status: values.status || "scheduled",
    };
    try {
      if (isNew) {
        await createMatch(payload);
        message.success("已创建");
      } else {
        await updateMatch(id!, payload);
        message.success("已保存");
      }
      navigate("/matches");
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  return (
    <Card title={isNew ? "新建比赛" : "编辑比赛"} loading={loading}>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ status: "scheduled" }}
        onFinish={onFinish}
        style={{ maxWidth: 640 }}
      >
        <Form.Item name="name" label="名称">
          <Input placeholder="可选" />
        </Form.Item>
        <Form.Item name="tournament" label="赛事">
          <Input placeholder="赛事名" />
        </Form.Item>
        <Form.Item name="event_round" label="轮次">
          <Input placeholder="如 R16、决赛" />
        </Form.Item>
        <Form.Item name="home_side" label="主场标识">
          <Input />
        </Form.Item>
        <Form.Item name="away_side" label="客场标识">
          <Input />
        </Form.Item>
        <Form.Item name="player1_id" label="球员 1">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            options={playerOptions}
            loading={playersLoading}
            placeholder="选择球员"
          />
        </Form.Item>
        <Form.Item name="player2_id" label="球员 2">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            options={playerOptions}
            loading={playersLoading}
            placeholder="选择球员"
          />
        </Form.Item>
        <Form.Item name="score" label="比分">
          <Input placeholder="如 6-4 6-3" />
        </Form.Item>
        <Form.Item name="venue" label="场地">
          <Input />
        </Form.Item>
        <Form.Item name="scheduled_at" label="开赛时间">
          <DatePicker showTime style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="status" label="状态" rules={[{ required: true }]}>
          <Select options={statusOptions} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
            <Link to="/matches">返回列表</Link>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
}
