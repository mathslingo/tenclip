# 全量笔记表（推荐用 10 位 note_id）

> 2026-09-19。业务库仍分 `social.db`（用户笔记）与 `news_feed.db`（资讯）；本表是推荐侧的**统一 item 目录**。

## 目标

| 项 | 约定 |
| --- | --- |
| 库 | `data/rec_notes.db` 表 `rec_notes` |
| 主键 | `note_id` **恰好 10 位数字**（`1000000000` 起递增，字符串存） |
| 来源 | `source_kind=user_note` / `news` |
| 溯源 | `source_ref` 唯一：`user:{social.notes.id}` 或 `news:{news_articles.id}` |
| 不替换 | 小程序现有 `notes.id`（16 位 hex）与资讯自增 id **保持不变** |

后续算法推荐只认 `note_id`；社交/抓取库继续各写各的，入库后同步到本表。

## 同步

1. **启动回填**：`init_rec_catalog()` 把已有笔记 + 资讯 upsert 进来（已有 `source_ref` 不换 id）。
2. **发笔记**：`create_note` 成功后写入；删除笔记则 `status=deleted`。
3. **抓取**：`ingest_news` 结束后按 `news_articles` 全量 upsert（条数少，幂等）。

## 暂不改

发现页 `/api/news/feed` 仍走原来的混排。M1 召回切到本表后再接 embedding / 曝光日志。
