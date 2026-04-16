from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SFT_FILE = "mock_tennis_qwen2_vl_mm_sft_1k.json"
DPO_FILE = "mock_tennis_qwen2_vl_mm_dpo_1k.json"

TOPICS = [
    "正手稳定性",
    "反手击球",
    "发球节奏",
    "接发站位",
    "步法启动",
    "击球点选择",
]

SCENARIOS = [
    "业余球员正手连续拉球训练",
    "双打接发回合训练",
    "发球后第一拍衔接练习",
    "底线对拉中的防守反击练习",
]

ISSUES = [
    "击球点偏后",
    "引拍过大导致节奏慢",
    "还原不及时",
    "重心后仰",
    "拍面不稳定",
]

DRILLS = [
    "影子挥拍 3 组，每组 20 次",
    "半场控制球练习 12 分钟",
    "分腿垫步 + 第一启动 5 组",
    "发球一区/二区交替 40 球",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mock multimodal SFT/DPO datasets for Qwen2-VL.")
    parser.add_argument("--output-dir", default="data", help="Output directory.")
    parser.add_argument("--image-root", default="mock_images", help="Relative image root recorded in dataset rows.")
    parser.add_argument("--count", type=int, default=1000, help="Number of rows for each split.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def make_image_paths(image_root: str, idx: int) -> list[str]:
    # 仅生成“占位”图像路径，方便打通多模态字段流程；生产请替换为真实抽帧路径。
    return [
        f"{image_root}/session_{idx % 50:03d}/frame_{(idx * 3) % 120:04d}.jpg",
        f"{image_root}/session_{idx % 50:03d}/frame_{(idx * 3 + 1) % 120:04d}.jpg",
        f"{image_root}/session_{idx % 50:03d}/frame_{(idx * 3 + 2) % 120:04d}.jpg",
    ]


def make_sft_row(rng: random.Random, idx: int, image_root: str) -> dict[str, object]:
    topic = rng.choice(TOPICS)
    scenario = rng.choice(SCENARIOS)
    issue = rng.choice(ISSUES)
    drill_a, drill_b = rng.sample(DRILLS, 2)
    return {
        "instruction": f"请基于图像序列分析{topic}，输出可执行训练建议。",
        "input": (
            f"场景：{scenario}。\n"
            f"主要问题：{issue}。\n"
            "请按“动作判断 / 关键问题 / 训练计划 / 下次拍摄建议”输出。"
        ),
        "output": (
            f"动作判断：当前{topic}存在节奏与击球点不稳定，核心风险是{issue}。\n"
            "关键问题：1) 准备偏慢；2) 击球点不够靠前；3) 击球后还原节奏断档。\n"
            f"训练计划：先做“{drill_a}”，再做“{drill_b}”，每次训练后记录稳定回合数。\n"
            "下次拍摄建议：固定侧后方机位，保留完整准备-击球-还原阶段。"
        ),
        "images": make_image_paths(image_root, idx),
    }


def make_dpo_row(rng: random.Random, idx: int, image_root: str) -> dict[str, object]:
    topic = rng.choice(TOPICS)
    scenario = rng.choice(SCENARIOS)
    issue = rng.choice(ISSUES)
    drill_a, drill_b = rng.sample(DRILLS, 2)
    chosen = (
        f"围绕{topic}，优先处理{issue}。\n"
        "先给结论：当前动作可继续训练，但必须先稳住节奏与还原。\n"
        f"训练建议：先“{drill_a}”，再“{drill_b}”；每组结束记录命中率和主观用力感。\n"
        "复盘重点：是否更容易在比赛节奏中复现，而不是单次击球看起来更用力。"
    )
    rejected = (
        f"{topic}问题不大，直接加大强度即可。\n"
        "不需要拆分问题，也不需要记录数据，感觉好就继续冲强度。"
    )
    return {
        "instruction": f"请基于图像序列给出{topic}训练建议，并提供偏好对样本。",
        "input": f"场景：{scenario}；当前限制：每次训练 45 分钟；问题：{issue}。",
        "chosen": chosen,
        "rejected": rejected,
        "images": make_image_paths(image_root, idx),
    }


def write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    out_dir = Path(args.output_dir)

    sft_rows = [make_sft_row(rng, i, args.image_root) for i in range(args.count)]
    dpo_rows = [make_dpo_row(rng, i, args.image_root) for i in range(args.count)]

    write_json(out_dir / SFT_FILE, sft_rows)
    write_json(out_dir / DPO_FILE, dpo_rows)

    print(f"[OK] Wrote {len(sft_rows)} multimodal SFT rows -> {(out_dir / SFT_FILE).resolve()}")
    print(f"[OK] Wrote {len(dpo_rows)} multimodal DPO rows -> {(out_dir / DPO_FILE).resolve()}")


if __name__ == "__main__":
    main()
