# YOLO Pose · ONNX Runtime Web（对齐参考 UI）

三按钮：**开始摄像头** / **选择图片** / **跑测试图(bus.jpg)**  
绿框 + `person xx%` + 红点关键点 + 青线骨架；状态「检测完成：N 个人」与 `persons: N | 推理 XXms`。

## 环境

**务必用独立 venv**，不要装进已有 `mmpose` / `openxlab` 的 conda（会升 `filelock` 起冲突）。

```bash
cd pose/yolo-pose-web
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
python export_onnx.py              # → models/yolo11n-pose.onnx @ 640
python download_assets.py          # → assets/bus.jpg
python3 -m http.server 8765
```

若已误装进共享环境：`pip install 'filelock~=3.14.0'` 可恢复 openxlab。

本机：`http://127.0.0.1:8765/` · 真机用 HTTPS（见下）。

可选：`?imgsz=320&model=./models/yolo11n-pose.onnx`（须与导出一致）。

## 公网 HTTPS（推荐）

Nginx 静态反代，**不必**再跑 `http.server`。

1. 确认已导出模型与测试图：
   ```bash
   ls /root/code/tenclip/pose/yolo-pose-web/models/yolo11n-pose.onnx
   ls /root/code/tenclip/pose/yolo-pose-web/assets/bus.jpg
   ```

2. 宝塔 → 网站 → `api.uchance.tech` → 配置文件，在 `location /` **之前**粘贴：

```nginx
location = /yolo-pose {
    return 301 /yolo-pose/;
}
location ^~ /yolo-pose/ {
    alias /root/code/tenclip/pose/yolo-pose-web/;
    index index.html;
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
}
```

完整示例：`scripts/deploy/nginx-yolo-pose.conf.example`

3. 重载：
```bash
nginx -t && nginx -s reload
# 宝塔：/www/server/nginx/sbin/nginx -t && /www/server/nginx/sbin/nginx -s reload
```

4. 验证：
```bash
curl -sI https://api.uchance.tech/yolo-pose/
curl -sI https://api.uchance.tech/yolo-pose/app.js
curl -sI https://api.uchance.tech/yolo-pose/models/yolo11n-pose.onnx
```
手机 Safari 打开：`https://api.uchance.tech/yolo-pose/`

## 行为

| 项 | 说明 |
|----|------|
| 输入 | 默认 640×640 letterbox |
| NMS | conf / IoU，最多 20 人 |
| 缓存 | 模型写入 IndexedDB，二次启动更快 |
| iOS | HTTPS、手势开摄像头、playsinline、≤30 FPS |
