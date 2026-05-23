import { PlusOutlined } from "@ant-design/icons";
import { App, Button, Popconfirm, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { deleteMatch, listMatches } from "../../api/resources";
import type { Match } from "../../api/types";

export function MatchList() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Match[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listMatches(page, pageSize);
      setData(res.items);
      setTotal(res.pagination.total);
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [message, page, pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: ColumnsType<Match> = [
    {
      title: "名称",
      dataIndex: "name",
      ellipsis: true,
      render: (t: string | null, r) => (
        <Link to={`/matches/${r.id}`}>{t || r.tournament || r.id.slice(0, 8)}</Link>
      ),
    },
    { title: "赛事", dataIndex: "tournament", width: 160, ellipsis: true },
    { title: "轮次", dataIndex: "event_round", width: 100, render: (x) => x ?? "—" },
    { title: "比分", dataIndex: "score", width: 120, render: (x) => x ?? "—" },
    { title: "状态", dataIndex: "status", width: 100 },
    {
      title: "开赛时间",
      dataIndex: "scheduled_at",
      width: 170,
      render: (d: string | null) => (d ? dayjs(d).format("YYYY-MM-DD HH:mm") : "—"),
    },
    {
      title: "操作",
      key: "actions",
      width: 160,
      render: (_, r) => (
        <Space>
          <Link to={`/matches/${r.id}`}>编辑</Link>
          <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
            <Typography.Link type="danger">删除</Typography.Link>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  async function onDelete(id: string) {
    try {
      await deleteMatch(id);
      message.success("已删除");
      void load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "删除失败");
    }
  }

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/matches/new")}>
          新建比赛
        </Button>
      </Space>
      <Table<Match>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />
    </>
  );
}
