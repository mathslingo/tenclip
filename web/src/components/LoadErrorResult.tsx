import { Button, Result, Space } from "antd";
import { useNavigate } from "react-router-dom";

type Props = {
  /** 错误说明（接口返回或兜底文案） */
  subTitle: string;
  onRetry?: () => void;
  retryLoading?: boolean;
};

/** 整页加载失败：结果态 + 重试 + 回首页 */
export function LoadErrorResult({ subTitle, onRetry, retryLoading }: Props) {
  const navigate = useNavigate();
  return (
    <div style={{ maxWidth: 560, margin: "48px auto", padding: 16 }}>
      <Result
        status="error"
        title="加载失败"
        subTitle={subTitle}
        extra={
          <Space wrap>
            {onRetry ? (
              <Button type="primary" loading={!!retryLoading} onClick={onRetry}>
                重试
              </Button>
            ) : null}
            <Button onClick={() => navigate("/")}>返回首页</Button>
          </Space>
        }
      />
    </div>
  );
}
