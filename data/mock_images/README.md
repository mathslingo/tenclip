# mock_images

该目录用于承载 Qwen2-VL 多模态训练样本中的图像路径（占位）。

- `scripts/generate_mock_vlm_datasets.py` 会在数据里写入类似 `mock_images/session_xxx/frame_xxxx.jpg` 的相对路径；
- 当前仓库不自动生成真实图片，仅用于打通 LLaMA-Factory 多模态字段流程；
- 实际训练前请用真实抽帧文件替换这些路径，或按相同路径结构放入图片。
