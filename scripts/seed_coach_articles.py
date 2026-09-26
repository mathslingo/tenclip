"""写入 10 篇自有网球教学图文。重复执行会按 url 更新标题和正文。"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.news_feed import DB_PATH, init_news_db  # noqa: E402
from services.poster import poster_url  # noqa: E402

SOURCE = "UChance 教学"
DOMAIN = "tenclip.coach"
# 早于当天新闻，避免占住发现页最前面；教学页由接口另行附上。
BASE = datetime(2026, 9, 25, 18, 0, tzinfo=timezone(timedelta(hours=8)))

ARTICLES = [
    {
        "slug": "forehand-shoulder",
        "title": "正手训练：先转肩，再甩拍",
        "tags": "教学,网球,训练,正手",
        "summary": (
            "很多业余正手出界，问题不在最后一下甩腕，而在引拍时肩膀没转过去。拍头可以早一点离开来球，但胸要对着边线，非持拍肩对着来球。这样击球时是身体转回来带着拍子，而不是手臂单独往前推。\n\n"
            "练习时先不打球。侧身站好，把非持拍手指向来球方向，持拍手把拍头举到肩后，停两秒，再转到对网。做 20 次，感觉拍头是被转体甩出来的。\n\n"
            "上场后只要求一件事：来球在身体侧面击出，而不是追到身前再推。打不深没有关系，先把击球点固定在前脚旁边。连续 15 个落在发球区内，再加力。"
        ),
    },
    {
        "slug": "two-handed-backhand",
        "title": "反手训练：双手反拍用另一只手送拍头",
        "tags": "教学,网球,训练,反手",
        "summary": (
            "双手反拍最常见的毛病，是持拍手一直在主导，另一只手只是扶着。结果拍面打开，球飘、下网，或者被迫用手腕去翻。非持拍手才应该把拍头送向来球的前方。\n\n"
            "引拍时，前肩转向球网侧面，拍头不要掉到膝盖下面。向前挥时，想象非持拍手的掌心把拍柄往前送，持拍手负责不让拍面晃。击球后拍头收到异侧肩上，而不是停在身前。\n\n"
            "对墙或喂球时，先用七成力打直线，专打反手位腰部高度。如果球总是偏高，多半是拍头掉了，把非持拍手抬高一点再送。"
        ),
    },
    {
        "slug": "toss",
        "title": "发球训练：抛球只练高度和位置",
        "tags": "教学,网球,训练,发球",
        "summary": (
            "发球不稳，先别改握拍和引拍，先把抛球固定。抛球手伸直，球从指尖送出，而不是手腕向上甩。球应落在前脚前方略靠持拍侧，高度大约比击球点再高一个球拍。\n\n"
            "先不挥拍。连续抛 30 个，让球落在拍面上，拍子平放在你打算击球的位置。能落进拍面里 20 个以上，再把挥拍加回来。\n\n"
            "抛歪了就放下重抛，不要追着去够。追球会让肩膀打开过早，球不是下网就是出底线。一发和二发可以共用同一个抛球点，差别放在刷球的高度上。"
        ),
    },
    {
        "slug": "second-serve",
        "title": "发球训练：二发用上旋，而不是减力推",
        "tags": "教学,网球,训练,发球",
        "summary": (
            "二发怕失误时，最容易变成把拍面打平、往框里推。球速下来了，但落点浅，对方可以直接抢攻。二发要保留向上刷的动作，让球自己旋转过网。\n\n"
            "抛球比一发略靠前，击球时拍头从球的右下（右手持拍）刷向左上，拍面在接触时仍稍稍朝上。目标不是追速度，而是让球过网后明显下坠，第二落点在发球线后两米以内。\n\n"
            "一组 10 个二发，只记进区个数和第二个落点。进 7 个、且没有一个停在发球线上，这组才算过。力量可以小，刷球的轨迹不要小。"
        ),
    },
    {
        "slug": "volley",
        "title": "截击训练：拍头高于手腕，向前挡",
        "tags": "教学,网球,训练",
        "summary": (
            "截击不是小正手。拍头要高于手腕，拍面略开，身体侧对来球，向前迎一小步把球挡深。向后引拍越大，越容易把球打出底线，或者漏在拍框上。\n\n"
            "离墙两米，喂球人抛腰部高的球。你只做分腿、侧身、拍头立住、向前送 20 厘米。每组 15 个，左右手各做。能听到短促的碰球声，而不是挥扫的声音，动作就对了。\n\n"
            "上网后站在发球线与球网中间，不要贴网。对方回球深时，你仍有一步去挡；贴太近，高球会从你头顶过去。"
        ),
    },
    {
        "slug": "split-step",
        "title": "步法训练：对方击球瞬间做分腿垫步",
        "tags": "教学,网球,训练,步法",
        "summary": (
            "跑得慢，常常不是步子小，而是启动晚。对方球拍碰到球的那一下，你的双脚要刚好离地再落地，这就是分腿垫步。落地时重心在前脚掌，膝盖微弯，下一拍才能向任意方向跨出。\n\n"
            "可以不打球，看同伴挥拍。他的拍子碰到想象中的球时，你垫一步。晚了就重来。连续对上 20 次，再上场。\n\n"
            "垫步之后只跨一步去够球，不要垫完还在原地看。来球很近时，这一步是小的调整步；来球很远时，第一下就要侧身打开髋，而不是面对球网往旁边蹭。"
        ),
    },
    {
        "slug": "rally-target",
        "title": "底线训练：把球打到让对方回头",
        "tags": "教学,网球,训练",
        "summary": (
            "对拉打不长，多半是每拍都往对方正中间送，对方不用动，你却越打越急。相持先选一个大目标：反手深区或正手外侧，让对方多走一步。\n\n"
            "和同伴约定，前 20 拍只打斜线，落点过发球线、靠近单打边线内侧一米。出界可以，下网要立刻减力。斜线稳定后，再允许一拍变直线，而且变线前必须有两拍打深的斜线。\n\n"
            "自己对墙时，在墙上贴一张纸当目标，纸的位置偏左或偏右，不要贴在正中。打中纸不重要，重要的是拍面每次都朝那个方向送。"
        ),
    },
    {
        "slug": "topspin",
        "title": "上旋训练：拍头从低处刷到高处",
        "tags": "教学,网球,训练",
        "summary": (
            "上旋不是手腕在击球瞬间突然一翻。拍头从球的后下方开始，向前上方刷过球的后部，结束时拍头高过另一侧肩膀。球过网要有余量，下落才明显。\n\n"
            "先用半速打。如果球贴网飞、几乎不往下掉，说明拍面太关、轨迹太平。把跟随动作做完整，拍头收到肩上，再看第二落点是不是比刚才更靠近底线前。\n\n"
            "不要一上来就刷到出界。先要求 10 个球都过网并落在对方场内，再逐渐加刷球的高度。能控制落点之后，上旋自然会带出深度。"
        ),
    },
    {
        "slug": "doubles-positions",
        "title": "双打站位：发球方一人留底线一人上网",
        "tags": "教学,网球,训练,双打站位",
        "summary": (
            "业余双打最乱的是四个人都站在底线，或者两个人同时冲到网前挡同一条线。发球这方，发球的人先留在底线完成发球和第一拍，同伴站在发球线附近、略偏另一条线，准备截击。\n\n"
            "一发进区后，发球的人根据回球再决定上不上网，不要发球动作还没结束就往前跑。网前的人只负责自己这半边的低球和中路偏自己的球，另一半留给同伴。\n\n"
            "接发球方也可以一人底线一人网前。网前的人在同伴接发时稍蹲，拍头立住，防的是对方网前的人偷袭直线。先把这四个位置站熟，再谈轮转。"
        ),
    },
    {
        "slug": "court-pace",
        "title": "场地训练：硬地提前准备，红土多留一步",
        "tags": "教学,网球,训练",
        "summary": (
            "同一套正手，换场地会觉得完全不一样。硬地球速快、弹跳高，引拍要在球过网时就开始，击球点更靠前。等球弹到最高点再挥，往往已经晚了。\n\n"
            "红土球速慢、弹跳不规则，可以多滑一步再击球，但拍面不要因此打开去捞。落地后允许小碎步调整，击球仍然打在身体侧面。草地低而快，引拍更短，步法以小垫步为主，不要大跨步追已贴地的球。\n\n"
            "换场地的第一组对拉，只打七成力，专门找击球点。适应了弹跳再加深度。场地变了，转肩和分腿垫步不用变。"
        ),
    },
]


def main() -> None:
    init_news_db()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        for i, art in enumerate(ARTICLES):
            published = (BASE - timedelta(minutes=20 * i)).isoformat()
            url = f"https://tenclip.local/coach/{art['slug']}"
            conn.execute(
                """
                INSERT INTO news_articles (
                    source, source_domain, source_tier, title, summary, url,
                    image_url, tags_csv, published_at, ingested_at, popularity
                ) VALUES (?, ?, 2, ?, ?, ?, '', ?, ?, ?, 0)
                ON CONFLICT(url) DO UPDATE SET
                    source=excluded.source,
                    source_domain=excluded.source_domain,
                    title=excluded.title,
                    summary=excluded.summary,
                    tags_csv=excluded.tags_csv,
                    published_at=excluded.published_at
                """,
                (
                    SOURCE,
                    DOMAIN,
                    art["title"],
                    art["summary"],
                    url,
                    art["tags"],
                    published,
                    now,
                ),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT id, title, url FROM news_articles WHERE source_domain=?",
            (DOMAIN,),
        ).fetchall()
        for row_id, title, url in rows:
            slug = url.rsplit("/", 1)[-1]
            img = poster_url("news", f"coach-{slug}", title)
            if img:
                conn.execute(
                    "UPDATE news_articles SET image_url=? WHERE id=?",
                    (img, row_id),
                )
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM news_articles WHERE source_domain=?",
            (DOMAIN,),
        ).fetchone()[0]
    print(f"coach articles: {n}")


if __name__ == "__main__":
    main()
