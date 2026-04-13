from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


SFT_FILE = "mock_tennis_sft_10k.json"
DPO_FILE = "mock_tennis_dpo_10k.json"
DATASET_INFO_FILE = "dataset_info.json"

TOPICS = [
    "正手稳定性",
    "反手击球",
    "发球节奏",
    "二发安全性",
    "截击时机",
    "步法启动",
    "落点控制",
    "比赛心态",
    "接发站位",
    "体能恢复",
    "训练计划",
    "动作纠错",
    "视频复盘",
    "击球高度",
    "拍面控制",
    "随挥完整度",
]

SCENARIOS = [
    "一位刚学网球 3 个月的成人爱好者",
    "一位每周训练 2 次的大学生球员",
    "一位准备参加校内比赛的初级选手",
    "一位反手容易失误的业余球员",
    "一位发球速度不错但稳定性不足的选手",
    "一位希望通过视频分析提升动作效率的用户",
    "一位经常在比赛中紧张的俱乐部球员",
    "一位膝盖有轻微不适、需要控制训练量的爱好者",
]

GOALS = [
    "提升稳定性",
    "减少非受迫性失误",
    "建立更清晰的训练重点",
    "在 4 周内看到可感知进步",
    "形成可复用的比赛策略",
    "让动作更省力",
    "改善节奏感和击球点",
    "提高复盘效率",
]

CONSTRAINTS = [
    "每次训练只有 45 分钟",
    "只有一台手机可以录视频",
    "没有固定教练带练",
    "训练场地经常风比较大",
    "只能在周末进行高强度训练",
    "希望尽量避免肩部负担过大",
    "希望方案适合单人练习",
    "预算有限，不考虑额外器材",
]

SUGGESTIONS = [
    "先稳定击球节奏，再追求力量增长",
    "优先保证击球点在身体前侧",
    "减少大幅度后仰，保持重心向前",
    "让引拍更简洁，避免多余动作",
    "每次训练只抓 1 到 2 个关键问题",
    "把视频拆成准备、击球、还原三个阶段看",
    "用固定的自检问题提升复盘质量",
    "先建立高概率回合模式，再增加变化",
]

DRILLS = [
    "影子挥拍 3 组，每组 20 次",
    "底线连续对拉 10 分钟，目标是 20 拍不断",
    "定点落点练习 6 组，每组 12 球",
    "发球一区 / 二区交替练习 40 球",
    "分腿垫步加第一步启动练习 5 组",
    "半场控制球练习 15 分钟",
    "手机慢动作录制 5 分钟并复盘",
    "接发站位前后各调整半步做对照测试",
]

BAD_PATTERNS = [
    "只要多练就一定会好，不需要具体方法。",
    "直接全力打就行，动作细节不用在意。",
    "你应该把所有技术问题一次性全部改掉。",
    "比赛紧张时不要想太多，顺其自然就行。",
    "先追求速度，稳定性可以以后再补。",
    "训练越累越有效，不需要安排恢复。",
    "视频没必要复盘，看感觉就够了。",
    "如果今天状态不好，就把训练量翻倍。",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mock Alpaca-format SFT and DPO datasets.")
    parser.add_argument("--output-dir", default="data", help="Directory to write datasets into.")
    parser.add_argument("--sft-count", type=int, default=10_000, help="Number of SFT records to generate.")
    parser.add_argument("--dpo-count", type=int, default=10_000, help="Number of DPO records to generate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible generation.")
    return parser.parse_args()


def _pick(rng: random.Random, values: list[str], n: int) -> list[str]:
    return rng.sample(values, k=n)


def make_sft_record(idx: int, rng: random.Random) -> dict[str, str]:
    topic = rng.choice(TOPICS)
    scenario = rng.choice(SCENARIOS)
    goal = rng.choice(GOALS)
    constraint = rng.choice(CONSTRAINTS)
    suggestion_a, suggestion_b = _pick(rng, SUGGESTIONS, 2)
    drill_a, drill_b = _pick(rng, DRILLS, 2)

    instruction = f"请针对{topic}给出一份可执行的中文训练建议。"
    input_text = (
        f"场景：{scenario}。\n"
        f"目标：{goal}。\n"
        f"限制：{constraint}。\n"
        f"请输出：问题判断、动作建议、训练安排、复盘要点。"
    )
    output = (
        f"可以先把{topic}拆成“问题判断、动作调整、训练安排、复盘标准”四部分处理。\n"
        f"1. 问题判断：先确认当前最影响效果的是节奏、击球点还是还原速度，不要一次改太多。\n"
        f"2. 动作建议：{suggestion_a}；同时，{suggestion_b}。\n"
        f"3. 训练安排：本周优先做“{drill_a}”和“{drill_b}”，每次训练结束后记录成功率与主观感受。\n"
        f"4. 复盘要点：重点看准备是否及时、重心是否稳定、击球后是否能快速还原。\n"
        f"5. 执行建议：连续练 2 周后再决定是否提高强度，避免因为短期波动频繁改动作。\n"
        f"示例编号：SFT-{idx:05d}。"
    )
    return {"instruction": instruction, "input": input_text, "output": output}


def make_dpo_record(idx: int, rng: random.Random) -> dict[str, str]:
    topic = rng.choice(TOPICS)
    scenario = rng.choice(SCENARIOS)
    goal = rng.choice(GOALS)
    constraint = rng.choice(CONSTRAINTS)
    suggestion_a, suggestion_b = _pick(rng, SUGGESTIONS, 2)
    drill_a, drill_b = _pick(rng, DRILLS, 2)
    bad = rng.choice(BAD_PATTERNS)

    instruction = f"请为{topic}生成一段适合 DPO 训练的中文问答偏好样本。"
    input_text = (
        f"用户画像：{scenario}。\n"
        f"训练目标：{goal}。\n"
        f"现实限制：{constraint}。\n"
        f"要求：给出一个更优回答和一个较差回答，风格都像教练建议。"
    )
    chosen = (
        f"更优回答：\n"
        f"围绕{topic}，建议先明确单一优先级，再安排可执行训练。\n"
        f"- 先判断最突出的问题，避免同时改太多变量。\n"
        f"- 动作上建议{suggestion_a}，并且{suggestion_b}。\n"
        f"- 训练上可安排“{drill_a}”与“{drill_b}”，每次训练后用 1 分钟记录命中率和稳定性。\n"
        f"- 如果受限于“{constraint}”，就把重点放在高频、小步快跑式改进，而不是追求一次解决全部问题。\n"
        f"- 复盘时优先看是否更稳定、是否更省力、是否更容易在比赛中复现。\n"
        f"样本编号：DPO-{idx:05d}。"
    )
    rejected = (
        f"较差回答：\n"
        f"{bad}\n"
        f"关于{topic}不用分步骤，也不用记录数据，想到什么练什么即可。\n"
        f"如果训练受限于“{constraint}”，那就把强度再拉高一点试试。"
    )
    return {
        "instruction": instruction,
        "input": input_text,
        "chosen": chosen,
        "rejected": rejected,
    }


def write_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_dataset_info(path: Path) -> None:
    dataset_info = {
        "mock_tennis_sft_10k": {
            "file_name": SFT_FILE,
        },
        "mock_tennis_dpo_10k": {
            "file_name": DPO_FILE,
            "ranking": True,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "chosen": "chosen",
                "rejected": "rejected",
            },
        },
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    output_dir = Path(args.output_dir)

    sft_rows = [make_sft_record(i, rng) for i in range(args.sft_count)]
    dpo_rows = [make_dpo_record(i, rng) for i in range(args.dpo_count)]

    write_json(output_dir / SFT_FILE, sft_rows)
    write_json(output_dir / DPO_FILE, dpo_rows)
    write_dataset_info(output_dir / DATASET_INFO_FILE)

    print(f"[OK] Wrote {len(sft_rows)} SFT rows to {(output_dir / SFT_FILE).resolve()}")
    print(f"[OK] Wrote {len(dpo_rows)} DPO rows to {(output_dir / DPO_FILE).resolve()}")
    print(f"[OK] Wrote dataset info to {(output_dir / DATASET_INFO_FILE).resolve()}")


if __name__ == "__main__":
    main()
