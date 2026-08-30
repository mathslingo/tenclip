# YOLO Pose + Tennis · ONNX Runtime Web

按钮：**开始摄像头** / **选择图片** / **跑测试图(人物)** / **网球开·关** / **跑网球测试图**  
人体：绿框 + `person xx%` + 红点关键点 + 青线骨架；网球：黄框 + 轨迹 + 平面估速（球直径标定）。

## 环境

**推荐：复用本机 conda `mmpose_gpu`**（已有 torch / opencv / numpy 等，省磁盘；网球训练与 ONNX 导出也走这套）。

```bash
conda activate mmpose_gpu
cd pose/yolo-pose-web

# 仅补缺（常见缺 ultralytics）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple 'ultralytics>=8.3.0,<9'
# 若 openxlab 报错：pip install 'filelock~=3.14.0'

python export_onnx.py                 # → models/yolo11n-pose.onnx
python export_tennis_onnx.py          # → models/yolo11n-tennis.onnx（COCO sports ball）
python download_assets.py             # → assets/bus.jpg
# 可选：自备一张含网球的图 → assets/tennis-sample.jpg
python3 -m http.server 8765
```

打开 `http://127.0.0.1:8765/` → 点「网球」→ 摄像头或选图。无 tennis ONNX 时自动 **HSV 黄绿兜底**。

可选独立 `.venv`（不想动 conda 时）见下方历史说明；浏览器推理不依赖 Python。

可选 query：`?imgsz=640&tennisConf=0.2&tennisModel=./models/yolo11n-tennis.onnx`



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
| 姿态 | `yolo11n-pose.onnx`，绿框 + 骨架 |
| 网球 | 点「网球」加载 `yolo11n-tennis.onnx`（COCO **sports ball** 类）；失败则 HSV 黄绿兜底 |
| 轨迹 / 估速 | `lib/ball_tracker.js`：跨帧关联 + 球直径≈6.7cm → 米制距离 / km/h（平面近似） |
| 输入 | 默认 640×640 letterbox |
| 缓存 | 姿态 / 网球模型均写 IndexedDB |
| iOS | HTTPS、手势开摄像头、playsinline、≤30 FPS |

## 性能

### 耗时在哪

推理全部发生在**打开页面的那台设备**（手机 / 电脑）的浏览器里，云主机只用 Nginx 发静态文件。
所以云主机的 CPU / 内存 **不影响帧耗时**，只影响首次下载模型的速度。

```
云主机 Nginx  ──静态 html/js/onnx──►  浏览器 ONNX Runtime Web  ──► 每帧推理
```

开启网球后每帧**串行**跑两个 640 模型：

```
姿态 ~246ms  +  网球 ~221ms  ≈  整帧 480ms (~2 FPS)   ← iPhone Safari 实测量级
```

状态栏末尾显示当前后端：`[webgpu]` / `[wasm]` / `[wasm x4]`，可直接判断走了哪条路。

### 已实现的优化（不改模型、不降精度）

模型权重、`imgsz=640`、`conf` 阈值均未改动，输出与优化前一致。

| 手段 | 做法 | 预期 |
|------|------|------|
| **WebGPU 后端** | `createSession()` 优先 `executionProviders: ["webgpu"]`，失败自动回退 wasm；`?webgpu=0` 强制关闭 | 支持的设备常 2–5× |
| **WASM 多线程** | `numThreads` 按核数（上限 4），仅在 `self.crossOriginIsolated` 时启用 | 多核约 1.5–3× |
| **输入缓冲复用** | letterbox 不再逐帧 `new Float32Array(3×640×640)`（约 5MB） | 减少 GC 抖动 |
| **按需关模型** | 不看网球时关掉「网球」 | 单帧约减半 |

多线程依赖 `SharedArrayBuffer`，需要 Nginx 在 `/yolo-pose/` 里发跨源隔离头：

```nginx
add_header Cross-Origin-Opener-Policy "same-origin";
add_header Cross-Origin-Embedder-Policy "require-corp";
```

见 `scripts/deploy/nginx-yolo-pose.conf.example`。开了 COEP 后跨源脚本必须带 `crossorigin`，
`index.html` 里的 onnxruntime-web CDN 标签已加。**不配这两个头也能正常用**，只是退回单线程。

### 未来可选方案

按对精度的影响分三组。

**A. 不降精度（推荐优先做）**

| 方案 | 思路 | 代价 |
|------|------|------|
| **网球 ROI 裁剪** | 用上一帧球心在**原分辨率**上裁 320 区域再检测，跟丢时回退整帧 | 算量约 1/4，小球像素占比更大，**远距精度反而更好**；需处理跟丢/多球 |
| **Web Worker 推理** | 推理移出主线程（`ort.env.wasm.proxy`），主线程只画 | 帧耗时不变，但 UI 不卡、绘制更跟手 |
| **双 Worker 并行** | 姿态与网球各占一个 Worker 同时跑 | 理论上整帧≈max 而非 sum；内存翻倍，低端机可能反而更慢 |
| **预处理换 WebGL/WebGPU** | letterbox + 归一化改用 GPU，省掉 `getImageData` 与 JS 循环 | 省几十 ms；代码复杂度上升 |
| **升级 onnxruntime-web** | 新版 WASM/WebGPU 算子持续优化 | 需回归测试，注意 `ort.min.js` 与 `wasmPaths` 版本要一致 |
| **本地托管 ort 运行时** | 把 `dist/` 放到 `lib/ort/`，不依赖 CDN | 首屏更稳（国内 CDN 偶发慢），也省去 COEP 跨源顾虑 |

**B. 以精度换速度（按场景取舍）**

| 方案 | 思路 | 精度影响 |
|------|------|----------|
| `?imgsz=320` / `416` | 缩小输入 | 远处小球明显更易漏检 |
| 网球隔帧（2 姿态 : 1 网球） | 降低网球检测频率 | 单帧框仍准，但轨迹采样变稀 → 估速更抖 |
| FP16 / INT8 量化 | 导出时量化模型 | FP16 损失小、INT8 需校准，小目标风险较高 |
| 更小骨干 | 换 `yolov8n` 之类更轻的检测 | 直接掉 mAP |

**C. 精度方向（与速度无关，见 P2/P3）**

- 微调**单类 tennis ball** 模型替代 COCO `sports ball`（类 32）代理
- 球场线 / 手动标尺标定，替代球直径标定 → 估速更准
- 与手腕关键点耦合做击球分段

## 稳定性（.venv 会不会被回收？）

**不会。** `.venv` 只是磁盘上的目录，conda/系统不会自动删它。

| 角色 | 是否依赖 `.venv` |
|------|------------------|
| 浏览器 YOLO 推理 | 否（端侧 ONNX） |
| `python3 -m http.server` | 否（系统 Python 即可） |
| `export_onnx.py` | 是（装 ultralytics） |

真正会挂的是 **`nohup` 进程**：重启、手动 kill、偶发 OOM 后不会自动起来——与 venv 无关。

长期建议：
1. Nginx 直出 `/var/www/yolo-pose-web/`（无 Python，最稳），或  
2. `systemctl enable --now tenclip-yolo-pose-http`（见 `scripts/deploy/tenclip-yolo-pose-http.service`）保活 8765。

小程序「分析」→「实时关键点检测」→ 复制 `https://api.uchance.tech/yolo-pose/` 用系统浏览器打开。

---

## 方案：网球识别 + 飞行距离 / 球速预估

在现有 **人体关键点（YOLO11n-pose ONNX）** 之上，增加赛事视频里的 **黄绿色网球检测**，并用 **连续帧检测框** 估计飞行距离与近似球速。端侧仍走本目录的 ONNX Runtime Web，与姿态共用同一画布与摄像头管线。

### 目标与边界

| 目标 | 说明 |
|------|------|
| 识别 | 在人体骨架之上叠网球框（黄绿小球，常被运动模糊/遮挡） |
| 轨迹 | 跨帧关联同一颗球，画轨迹（可参考赛事分析里的多点尾迹可视化） |
| 距离 / 球速 | 由像素位移 → 米制位移 → km/h 或 m/s；精度依赖标定 |
| 非目标（v1） | 不要求专业鹰眼级 3D 重建；不强制服务端推理 |

### 总架构

```
摄像头 / 视频帧
    │
    ├─► [A] yolo11n-pose.onnx     → 人体框 + 17 关键点（已有）
    │
    └─► [B] tennis-detect.onnx    → 网球框 (cx,cy,w,h,conf)
              │
              ▼
         多帧关联 (BallTracker)
              │
              ▼
         像素位移 → 标定 → 飞行距离 / 瞬时·平均球速
              │
              ▼
         Canvas：人骨架(青) + 网球框(黄) + 轨迹 + HUD 数字
```

- **双模型并行**：姿态与网球分模型，避免「pose 头硬塞球类」效果差；网球模型可点按需加载（约 10–15MB），IndexedDB 缓存（与姿态相同策略）。
- **时序**：每帧先 letterbox → 可串行（姿态 → 网球）或隔帧网球（如 2 帧姿态 : 1 帧网球）保 FPS；目标整帧仍 ≥10 FPS（当前仅 pose 时约十余 FPS 量级）。
- **与人体联动（可选）**：球心靠近手腕/球拍区域时提高关联权重，减少场边黄物误检。

### 1）网球识别（黄绿色）

#### 推荐主路径：轻量检测 ONNX（类 YOLO detect）

| 项 | 建议 |
|----|------|
| 基模 | `yolo11n.pt` 或 `yolov8n.pt`，**单类 `tennis_ball`** 微调 / 蒸馏 |
| 数据 | 业余 + 赛事片段抽帧；含室内黄绿球场、运动模糊、半遮挡；HSV 难分时加难负样本（荧光线、广告牌） |
| 导出 | `export_onnx.py` 同款 imgsz（默认 640）；产出 `models/yolo11n-tennis.onnx` |
| 后处理 | conf / NMS；每帧最多保留 1–3 个高分框（单球场景取最高分或离上一轨迹最近者） |
| 前端 | 黄框 + `tennis xx%`；状态栏：`persons: N \| tennis: M \| 推理 …` |

黄绿色先验可作 **训练增强与弱监督**（标注时用颜色提示），线上仍以检测框为准，避免纯色阈值在光照/反光下崩掉。

#### 备选 / 兜底：HSV + 运动差分（无模型时）

1. 在 HSV 中取网球常见区间（H≈35–75，S/V 中高），形态学去噪得候选斑点。  
2. 与帧差/光流峰值求交，抑制静止黄物。  
3. 用外接圆/框当作「伪检测」。  

适合原型；正式赛事视频仍应切回 ONNX 检测。

#### 与现有 Pose Demo 的接入点

- `index.html`：增加「网球开/关」「跑网球测试图」；分辨率下拉与 pose 共用。  
- `app.js`：第二 session（或同一 ORT 环境双 session）；`runFrame` 内合并绘制。  
- 资源：`models/yolo11n-tennis.onnx`、`assets/tennis-sample.jpg`；按需 fetch + IDB。

### 2）连续框 → 飞行距离 / 球速

思路对齐 `highway/` 的「检测 → 跟踪 → 像素/米标定 → 速度」，但对象从车辆改为网球，标定物优先用 **球场线 / 球直径**。

#### 2.1 跨帧关联（BallTracker）

每帧取网球框中心 \(p_t = (c_x, c_y)\)（或底边中点）：

1. **贪心最近邻**：与上一活跃轨迹比欧氏距离，阈值随球速放大（如 `min(80px, 2·‖v̂‖·Δt)`）。  
2. **短时平滑**：EMA 或 2D 卡尔曼（位置 + 速度），抑制定位抖动（可参考 `highway/tracker.py`）。  
3. **生死**：连续丢失 \(N\) 帧（建议 8–15）结束轨迹；新高分框启动新轨迹。  
4. **击球分段**：球心速度突变或与手腕关键点距离骤降 → 切段，避免把「来球 + 回球」合成一条。

输出：轨迹点列 \(\{p_{t_i}\}\) 与时间戳 \(\{t_i\}\)（用 `performance.now()` 或视频 `currentTime`）。

#### 2.2 像素 → 米（标定，精度瓶颈）

任选其一（可并存，UI 里选模式）：

| 模式 | 方法 | 精度直觉 |
|------|------|----------|
| **A. 球直径** | 网球直径 ≈ 6.7 cm；用框宽/高均值估「像素/米」\(s = 0.067 / d_{px}\) | 近距尚可；远距框小误差大 |
| **B. 球场线** | 已知线段实长（单打边线宽 8.23 m、底线长 10.97 m 等），用户点两点或自动线检 | 侧面机位需透视，v1 可先假设近似俯视/固定机位 |
| **C. 手动标尺** | UI 拖一条「已知 1 m」线段 | 调试最快 |

得到尺度 \(s\)（米/像素）后：

\[
\Delta d_{\mathrm{px}} = \|p_t - p_{t-1}\|,\quad
\Delta d_{\mathrm{m}} = s \cdot \Delta d_{\mathrm{px}}
\]

飞行距离（一段轨迹）：\(D = \sum \Delta d_{\mathrm{m}}\)（可只统计「空中段」：球心高度相对底线有上升再下落）。

#### 2.3 球速

瞬时：\(v_t = \Delta d_{\mathrm{m}} / \Delta t\)（m/s），HUD 可显示 \(v_{\mathrm{km/h}} = v_t \times 3.6\)。  
平均：一段轨迹 \(D / (t_{\mathrm{end}}-t_{\mathrm{start}})\)。  
平滑：对 \(v_t\) 做 EMA（α≈0.5–0.7），过滤单帧跳变。

**注意**：单目、无滚转信息时，这是 **成像平面上的投影速度**，不是真实 3D 球速；机位越正对球路、标定越好，越接近观感球速。v1 产品文案写「估计球速 / 飞行距离（平面近似）」即可。

#### 2.4 HUD 建议

- `tennis: 1 | 轨迹长 4.2m | 估速 78 km/h | 推理 …`  
- 轨迹折线（黄/橙）+ 当前框；可选显示标定尺与 \(s\)。

### 实施分期

| 阶段 | 交付 | 验收 |
|------|------|------|
| **P0** | 网球 ONNX（COCO sports ball）+「网球」开关 + 黄框；无模型时 HSV 兜底 | **已实现**（`app.js` / `export_tennis_onnx.py` / `lib/ball_tracker.js`） |
| **P1** | BallTracker + 轨迹 + 球直径粗标定 + 估速 HUD | **已实现（平面近似）** |
| **P2** | 球场线/手动标尺 + 分段击球 | 待做 |
| **P3**（可选） | 与手腕关键点耦合、击球瞬间标记、导出轨迹 JSON | 待做 |

### 开发环境（网球相关）

统一用 **`conda activate mmpose_gpu`**：

| 用途 | 说明 |
|------|------|
| 训练 / 微调网球 detect | ultralytics（缺则 pip 补一次） |
| 导出 `yolo11n-tennis.onnx` | 同上 |
| 导出姿态 ONNX | `python export_onnx.py` |
| 浏览器推理 | **不依赖** conda；`http.server` 或 Nginx 即可 |

`mmpose_gpu` 里已有：`torch`、`opencv`、`numpy`、`pillow`、`scipy`、`matplotlib`、`pandas`、`tqdm` 等。通常只需补 **`ultralytics`**；若要用 sklearn 工具脚本再补 `scikit-learn`。  
装完 ultralytics 后若 `openxlab` 挂了：`pip install 'filelock~=3.14.0'`。

### 目录与接口（拟定）

```
pose/yolo-pose-web/
  models/yolo11n-pose.onnx      # 已有
  models/yolo11n-tennis.onnx    # 新增
  export_tennis_onnx.py         # 或 export_onnx.py --task detect --cls tennis
  app.js                        # 双 session + BallTracker
  lib/ball_tracker.js           # 关联 / 平滑 / 距离速度
```

导出示例（训练完成后，在 `mmpose_gpu` 中）：

```bash
conda activate mmpose_gpu
cd pose/yolo-pose-web
yolo export model=runs/detect/tennis/weights/best.pt format=onnx imgsz=640
# → 拷贝为 models/yolo11n-tennis.onnx
```

### 风险与对策

| 风险 | 对策 |
|------|------|
| 小球远距漏检 | imgsz 640；勿盲目 320；难例增广；必要时 ROI（人框周围裁剪再检） |
| 黄绿误检 | 难负样本；与 pose 手腕距离门控 |
| 标定不准导致球速虚高/虚低 | UI 暴露标定方式；默认球直径 + 可选标尺 |
| 双模拖垮 FPS | 网球隔帧；WebGPU；网球模型 nano |
| ultralytics 与 openxlab 冲突 | 钉 `filelock~=3.14.0`；勿无整包 `pip install -U` 乱升依赖 |

### 与 `highway/` 的关系

`tenclip/highway` 已具备「YOLO 检测 + 多目标跟踪 + 像素/米 + 速度」骨架，同样建议在 **`mmpose_gpu`** 下跑（`./setup_reuse_env.sh` 或只补 ultralytics）。算法可复用到 `ball_tracker.js`（前端）或离线批处理。**网球方案优先落在 `yolo-pose-web` 端侧**，与人体关键点 Demo 同一入口，便于小程序复制链接验证。

