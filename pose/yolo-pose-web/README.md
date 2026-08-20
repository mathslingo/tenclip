# YOLO Pose · ONNX Runtime Web（对齐参考 UI）

三按钮：**开始摄像头** / **选择图片** / **跑测试图(bus.jpg)**  
绿框 + `person xx%` + 红点关键点 + 青线骨架；状态「检测完成：N 个人」与 `persons: N | 推理 XXms`。

## 环境

```bash
cd pose/yolo-pose-web
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python export_onnx.py              # → models/yolo11n-pose.onnx @ 640
python download_assets.py          # → assets/bus.jpg
python3 -m http.server 8765
```

本机：`http://127.0.0.1:8765/` · 真机需 HTTPS。

可选：`?imgsz=320&model=./models/yolo11n-pose.onnx`（须与导出一致）。

## 行为

| 项 | 说明 |
|----|------|
| 输入 | 默认 640×640 letterbox |
| NMS | conf / IoU，最多 20 人 |
| 缓存 | 模型写入 IndexedDB，二次启动更快 |
| iOS | HTTPS、手势开摄像头、playsinline、≤30 FPS |
