#!/usr/bin/env bash
# 一键导出姿态 + 网球 ONNX（复用 mmpose_gpu，权重优先本地/镜像）
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
fi
conda activate mmpose_gpu

pkill -f 'python export_onnx.py' 2>/dev/null || true
pkill -f 'python export_tennis_onnx.py' 2>/dev/null || true

mkdir -p models
python -c "import ultralytics; print('ultralytics', ultralytics.__version__)"

download() {
  local url="$1" out="$2"
  [[ -f "$out" ]] && echo "已有 $out" && return 0
  echo "下载 $out …"
  # 直连 → ghproxy 镜像
  if curl -L --connect-timeout 20 --max-time 180 -o "$out.part" "$url"; then
    mv "$out.part" "$out"
    return 0
  fi
  rm -f "$out.part"
  local mirror="https://ghproxy.com/${url}"
  echo "直连失败，试镜像: $mirror"
  curl -L --connect-timeout 20 --max-time 180 -o "$out.part" "$mirror"
  mv "$out.part" "$out"
}

POSE_PT="yolo11n-pose.pt"
DET_PT="yolo11n.pt"
BASE="https://github.com/ultralytics/assets/releases/download/v8.4.0"

# 复用缓存
for cand in \
  "$HOME/.cache/ultralytics/$POSE_PT" \
  "$HOME/.ultralytics/$POSE_PT" \
  "./$POSE_PT"
do
  if [[ -f "$cand" && ! -f "./$POSE_PT" ]]; then
    cp -n "$cand" "./$POSE_PT" || true
  fi
done
for cand in \
  "$HOME/.cache/ultralytics/$DET_PT" \
  "$HOME/.ultralytics/$DET_PT" \
  "./$DET_PT" \
  "./yolov8n.pt"
do
  if [[ -f "$cand" ]]; then
    if [[ ! -f "./$DET_PT" ]]; then
      cp -n "$cand" "./$DET_PT" 2>/dev/null || cp -n "$cand" "./yolov8n.pt" || true
    fi
  fi
done

download "$BASE/$POSE_PT" "./$POSE_PT"
if [[ -f "./$DET_PT" ]]; then
  :
elif [[ -f "./yolov8n.pt" ]]; then
  DET_PT="yolov8n.pt"
else
  download "$BASE/yolo11n.pt" "./yolo11n.pt"
  DET_PT="yolo11n.pt"
fi

echo "==> 导出网球 detect ONNX"
python export_tennis_onnx.py --model "./$DET_PT"

echo "==> 导出姿态 ONNX"
python export_onnx.py --model "./$POSE_PT"

echo "==> 结果"
ls -lh models/
echo "完成。启动: python3 -m http.server 8765"
