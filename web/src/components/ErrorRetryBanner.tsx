import { Alert, Button } from "antd";

type Props = {
  message: string;
  onRetry: () => void;
  loading?: boolean;
};

/** 区块内错误提示 + 重试 */
export function ErrorRetryBanner({ message, onRetry, loading }: Props) {
  return (
    <Alert
      type="error"
      showIcon
      style={{ marginBottom: 16 }}
      message={message}
      action={
        <Button size="small" type="primary" loading={!!loading} onClick={onRetry}>
          重试
        </Button>
      }
    />
  );
}
