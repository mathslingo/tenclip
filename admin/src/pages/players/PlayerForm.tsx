import { App, Button, Card, Form, Input, InputNumber, Space } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { createPlayer, getPlayer, updatePlayer } from "../../api/resources";

export function PlayerForm() {
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
        const row = await getPlayer(id!);
        if (cancelled) return;
        form.setFieldsValue({
          display_name: row.display_name,
          country_code: row.country_code ?? undefined,
          ranking_points: row.ranking_points ?? undefined,
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
    display_name: string;
    country_code?: string;
    ranking_points?: number | null;
  }) {
    const payload = {
      display_name: values.display_name,
      country_code: values.country_code?.trim() || null,
      ranking_points: values.ranking_points ?? null,
    };
    try {
      if (isNew) {
        await createPlayer(payload);
        message.success("已创建");
      } else {
        await updatePlayer(id!, payload);
        message.success("已保存");
      }
      navigate("/players");
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "保存失败");
    }
  }

  return (
    <Card title={isNew ? "新建球员" : "编辑球员"} loading={loading}>
      <Form form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 480 }}>
        <Form.Item
          name="display_name"
          label="显示名称"
          rules={[{ required: true, message: "请输入名称" }]}
        >
          <Input placeholder="球员姓名" />
        </Form.Item>
        <Form.Item name="country_code" label="国家/地区代码">
          <Input placeholder="如 CN、US" maxLength={8} />
        </Form.Item>
        <Form.Item name="ranking_points" label="排名积分">
          <InputNumber style={{ width: "100%" }} placeholder="可选" />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
            <Link to="/players">返回列表</Link>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
}
