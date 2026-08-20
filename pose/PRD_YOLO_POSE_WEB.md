# PRD：端侧 YOLO Pose 实时（Safari / 小程序）

状态：demo 已落地，测帧率中  
版本：2026-08-20  
相关：`pose/yolo-pose-web/`

## 1. 背景

云 CPU RTMPose 单帧 500–800ms，无法跟手。改为端侧轻量 pose。

## 2. 方案

| 层 | 选择 |
|----|------|
| 模型 | YOLO11n-pose（或 YOLOv8n-pose），COCO 17 点 |
| 浏览器 | ONNX + onnxruntime-web（WASM），输入 320~416 |
| 快速验证 | Ultralytics 导出 ONNX；可选 NPM/tflite 对照 |
| 小程序 | 同一 ONNX + `wx.createInferenceSession`（Int8） |
| iOS | HTTPS、用户手势开摄像头、playsinline、≤30 FPS |

## 3. 本期交付

- [x] iPhone Safari demo：三按钮（摄像头 / 选图 / bus.jpg）
- [x] letterbox / NMS / 绿框+红点+青线骨架 / 推理耗时
- [x] IndexedDB 缓存模型；默认 imgsz=640
- [x] `export_onnx.py` + `download_assets.py`
- [ ] 真机记录 FPS（640 / 320）
- [ ] 微信小程序 session 复用同一后处理

## 4. 与录像回放

实时走本方案；长一点的离线骨架回放仍可用 `pose_server_v2` `/analyze-video`。
