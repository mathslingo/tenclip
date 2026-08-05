import { PlusOutlined } from "@ant-design/icons";
import { App, Button, Popconfirm, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { deletePlayer, listPlayers } from "../../api/resources";
import type { Player } from "../../api/types";

export function PlayerList() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Player[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listPlayers(page, pageSize);
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

  const columns: ColumnsType<Player> = [
    {
      title: "姓名",
      dataIndex: "display_name",
      render: (t: string, r) => <Link to={`/players/${r.id}`}>{t}</Link>,
    },
    { title: "国家/地区代码", dataIndex: "country_code", width: 140, render: (c) => c ?? "—" },
    {
      title: "积分",
      dataIndex: "ranking_points",
      width: 120,
      render: (p: number | null) => (p != null ? String(p) : "—"),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 180,
      render: (d: string) => dayjs(d).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "actions",
      width: 160,
      render: (_, r) => (
        <Space>
          <Link to={`/players/${r.id}`}>编辑</Link>
          <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
            <Typography.Link type="danger">删除</Typography.Link>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  async function onDelete(id: string) {
    try {
      await deletePlayer(id);
      message.success("已删除");
      void load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "删除失败");
    }
  }

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/players/new")}>
          新建球员
        </Button>
      </Space>
      <Table<Player>
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
