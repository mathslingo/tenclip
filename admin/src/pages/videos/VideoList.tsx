import { PlusOutlined } from "@ant-design/icons";
import { App, Button, Popconfirm, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { deleteVideo, listVideos } from "../../api/resources";
import type { Video } from "../../api/types";

export function VideoList() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Video[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listVideos(page, pageSize);
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

  const columns: ColumnsType<Video> = [
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (t: string | null, r) => {
        const uri = r.storage_uri;
        const fallback = uri.length > 48 ? `${uri.slice(0, 48)}…` : uri;
        return <Link to={`/videos/${r.id}`}>{t || fallback}</Link>;
      },
    },
    {
      title: "存储 URI",
      dataIndex: "storage_uri",
      ellipsis: true,
      width: 240,
    },
    {
      title: "时长(秒)",
      dataIndex: "duration_sec",
      width: 100,
      render: (s: number | null) => (s != null ? s : "—"),
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
          <Link to={`/videos/${r.id}`}>编辑</Link>
          <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
            <Typography.Link type="danger">删除</Typography.Link>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  async function onDelete(id: string) {
    try {
      await deleteVideo(id);
      message.success("已删除");
      void load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "删除失败");
    }
  }

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/videos/new")}>
          新建视频
        </Button>
      </Space>
      <Table<Video>
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
