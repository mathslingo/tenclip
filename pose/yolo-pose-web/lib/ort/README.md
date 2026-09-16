# onnxruntime-web dist（本机托管）

版本与页面锁定 **1.20.1**。体积较大，不进 git。

```bash
conda activate mmpose_gpu   # 或不进 conda，系统 python3 即可
cd pose/yolo-pose-web
python3 download_ort.py     # → lib/ort/ort.webgpu.min.js + *.wasm / *.mjs
```

Worker 与主线程回退都把 `ort.env.wasm.wasmPaths` 指到本目录。
