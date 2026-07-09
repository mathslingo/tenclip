# 实时推荐系统：学习清单与 TenClip 落地路线

> 场景：**网球资讯 feed + 视频/行为**（`services/news_feed.py`），要求 **在线低延迟**（目标 P99 &lt; 100–200ms 排序；召回可异步刷新）。  
> 立场：FM / Wide&Deep **未过时**，仍是精排基线；**生成式 / LLM** 是增量能力，不是一夜替换整个漏斗。

---

## 1. 目标架构（实时）

```text
[入库] RSS/HTML/视频元数据
    → 特征写入（item 向量、标签、时效）
[在线] 用户请求 /api/news/feed
    → 召回（毫秒级，ANN）→ 粗排（可选）→ 精排（轻量模型）→ 重排（规则/多样性）
    → 返回 JSON
[闭环] 曝光/点击/点赞/停留 → 日志 → 小时级/天级训练 → 热更新 embedding 或模型
```

| 阶段 | 延迟预算 | 典型技术 |
|------|----------|----------|
| 召回 | 5–20 ms | Redis 倒排 + FAISS/Milvus HNSW |
| 精排 | 20–50 ms | DeepFM / DIN 小模型、ONNX/Triton |
| 重排 | &lt;10 ms | MMR、来源多样性、时效衰减 |
| **LLM** | **不进主链路** | 离线打标签、冷启动 embedding、解释文案 |

---

## 2. 分阶段落地（TenClip）

### M0 — 当前（已有）

- `recommend_news()`：SQLite 全表扫描 + 规则分（时效 + 标签 + popularity）
- 适合：&lt; 几千条、开发验证
- 瓶颈：数据量上来后 **无法实时扩展**

### M1 — 实时 MVP（1–2 周，优先做）

**详细设计见 [`recsys-m1-design.md`](./recsys-m1-design.md)**（数据模型、FAISS、精排、API、实施排期）。

| 任务 | 做法 |
|------|------|
| Item 向量 | 标题+摘要 → `sentence-transformers` 或 API embedding，入库时算好 |
| 用户向量 | 最近点击/点赞文章的 embedding 平均或加权 |
| 召回 | **Milvus Lite / Redis + 内存 FAISS**，Top-K=200 |
| 精排 | **LightGBM** 或 **浅层 DeepFM**（特征：标签 overlap、时效、source_tier、popularity） |
| 在线 | `/api/news/feed` 只读索引 + 模型分，**不写 SQLite 全表扫** |
| 日志 | `news_feedback` 扩曝光表；落 `user_id, article_id, action, ts` |

### M2 — 序列与多目标（1–2 月）

| 任务 | 做法 |
|------|------|
| 序列 | 用户最近 N 次行为 → **SASRec 小模型** 或 DIN 式 attention |
| 多目标 | 点击 + 停留 + dislike 联合（ESMM / 多塔） |
| 近线 | Kafka/Redis Stream（或定时 5min job）更新用户向量 |
| 视频 | 视频标签/VLM 摘要 embedding 与资讯 **统一 item 空间** |

### M3 — LLM 增强（可选，不挡实时）

| 任务 | 做法 |
|------|------|
| 入库 | LLM 抽 tags、摘要、实体（**异步 batch**） |
| 冷启动 | 新文章仅文本 → 向量进索引，无需等行为 |
| 解释 | 「推荐理由」单独接口，**不阻塞 feed** |
| 探索 | Semantic ID / 小流量生成式 head（见下文论文） |

---

## 3. 必读综述（带链接，建议顺序）

### 3.1 总览与范式

| # | 文献 | 链接 | 读什么 |
|---|------|------|--------|
| 1 | **Large Language Models for Generative Recommendation** (Li et al., LREC 2024) | [ACL Anthology PDF](https://aclanthology.org/2024.lrec-main.886.pdf) | 生成式 vs 判别式；ID 化 item；任务 taxonomy |
| 2 | **A Survey on Generative Recommendation: Data, Model, and Tasks** (2025) | [arXiv HTML](https://arxiv.org/html/2510.27157v2) | LLM / LRM / Diffusion；数据–模型–任务三维 |
| 3 | **Foundation Model-Powered Recommender Systems** (2025) | [arXiv PDF](https://arxiv.org/pdf/2504.16420) | Feature → Generative → **Agentic** 三阶段 |
| 4 | **Recommender Systems Handbook** (Ricci et al.) | [Springer](https://link.springer.com/book/10.1007/978-1-4899-7637-6) | 经典漏斗、评估；作字典查 |

### 3.2 判别式基线（实时精排仍常用）

| # | 文献 | 链接 | 读什么 |
|---|------|------|--------|
| 5 | **Factorization Machines** (Rendle, 2010) | [PDF](https://www.csie.ntu.edu.tw/~b97053/paper/Rendle2010FM.pdf) | 稀疏特征交叉起点 |
| 6 | **Wide & Deep Learning** (Cheng et al., Google 2016) | [arXiv](https://arxiv.org/abs/1606.07792) | 记忆 + 泛化；工业精排模板 |
| 7 | **DeepFM** | [arXiv](https://arxiv.org/abs/1703.04247) | FM + DNN 联合 |
| 8 | **Deep Interest Network (DIN)** | [arXiv](https://arxiv.org/abs/1706.06978) | 行为序列 attention；实时特征工程参考 |
| 9 | **Self-Attentive Sequential Recommendation (SASRec)** | [arXiv](https://arxiv.org/abs/1808.09781) | 序列推荐 Transformer 基线 |
| 10 | **BERT4Rec** | [arXiv](https://arxiv.org/abs/1904.06690) | 双向序列；离线训练、在线取最后状态 |

### 3.3 召回与向量（实时必备）

| # | 文献 / 资源 | 链接 | 读什么 |
|---|-------------|------|--------|
| 11 | **Sampling-Bias-Corrected Neural Modeling (Sampled Softmax)** | [Google Research](https://research.google/pubs/pub48840/) | 大规模 softmax / 双塔训练 |
| 12 | **FAISS** (Meta) | [GitHub](https://github.com/facebookresearch/faiss) | HNSW/IVF；毫秒级 ANN |
| 13 | **Milvus** | [文档](https://milvus.io/docs) | 生产向量库；TenClip 可先用 Milvus Lite |
| 14 | **ScaNN** (Google) | [GitHub](https://github.com/google-research/google-research/tree/master/scann) | 召回 ANN 备选 |

### 3.4 生成式 / 大模型推荐（中长期）

| # | 文献 | 链接 | 读什么 |
|---|------|------|--------|
| 15 | **P5: Recommendation as Language Processing** | [arXiv](https://arxiv.org/abs/2203.13366) | Prompt 统一推荐任务 |
| 16 | **TALLRec** | [arXiv](https://arxiv.org/abs/2305.00447) | LLM 高效微调推荐 |
| 17 | **Actions Speak Louder than Words (HSTU)** | [arXiv](https://arxiv.org/abs/2402.17152) | Meta 大规模生成式序列 |
| 18 | **Generative Recommendation for Large-Scale Advertising (GR4AD)** | [arXiv](https://arxiv.org/pdf/2602.22732) | 工业：Semantic ID、延迟、在线 RL |
| 19 | **From Modularity to Unity (UniGenR)** | [ACM WWW 2026](https://dl.acm.org/doi/10.1145/3774904.3792842) | 统一生成式 ranking 与多任务 |

### 3.5 实时系统工程

| # | 资源 | 链接 | 读什么 |
|---|------|------|--------|
| 20 | **Monolith** (ByteDance 实时训练) | [arXiv](https://arxiv.org/abs/2209.07663) | 流式特征、实时训练思路 |
| 21 | **NVIDIA Triton Inference Server** | [文档](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/index.html) | 模型 serving、动态 batch |
| 22 | **Feast** (Feature Store) | [文档](https://docs.feast.dev/) | 在线/离线特征一致 |
| 23 | **《深度学习推荐系统》** 王喆 | [GitHub 笔记](https://github.com/wangzhegeek/DeepLearning-RecSys) | 中文工业全景 |

---

## 4. 开源实现（可直接试）

| 组件 | 项目 | 链接 | 用途 |
|------|------|------|------|
| 精排框架 | **DeepCTR-Torch** | [GitHub](https://github.com/shenweichen/DeepCTR-Torch) | DeepFM / DIN / DIEN 快速实验 |
| 序列 | **RecBole** | [GitHub](https://github.com/RUCAIBox/RecBole) | SASRec、BPR、统一评测 |
| 向量 | **sentence-transformers** | [文档](https://www.sbert.net/) | 资讯 title/summary embedding |
| ANN | **FAISS** | [GitHub](https://github.com/facebookresearch/faiss) | 单机召回 |
| Serving | **BentoML / Triton** | [BentoML](https://docs.bentoml.com/) | 模型 API 化 |
| 特征 | **Redis** | — | 用户最近行为、热门倒排 |

---

## 5. 实时推荐读法：4 周计划

| 周 | 主题 | 必读 | 动手 |
|----|------|------|------|
| **W1** | 漏斗 + 基线 | #5–8 + 王喆书 1–4 章 | 用 LightGBM 复现 `recommend_news` 特征 |
| **W2** | 向量召回 | #11–13 | title embedding + FAISS，P99 测延迟 |
| **W3** | 序列 | #9–10 | RecBole 跑 SASRec（离线），导出 user state |
| **W4** | LLM 边界 | #1–3 + #15–16 | 异步 LLM 打 tag，对比 M1 点击率 |

---

## 6. 评估指标（实时场景）

| 类型 | 指标 | 说明 |
|------|------|------|
| 离线 | AUC / GAUC、NDCG@K、HR@K | 时间切分，防泄漏 |
| 在线 | CTR、停留时长、 dislike 率 | A/B 或交错实验 |
| **系统** | **P50/P99 延迟**、QPS、召回命中率 | 实时硬指标 |
| 多样性 | ILD、来源覆盖率 | 资讯 feed 防单一源 |

工具：[Recommenders (Microsoft)](https://github.com/recommenders-team/recommenders) — 评测脚本参考。

---

## 7. TenClip 代码对照

| 模块 | 路径 | M1 改动建议 |
|------|------|-------------|
| 推荐入口 | `services/news_feed.py` → `recommend_news()` | 改为「召回 + 精排」两阶段 |
| API | `app.py` → `/api/news/feed` | 加 `Cache-Control`、分页不变 |
| 反馈 | `news_feedback` 表 | 增加 `impression` 曝光 |
| 配置 | `config/news_sources.json` | source_tier 作特征 |
| 视频 | `services/vlm_tennis.py` | 异步产出 tags，写入 item 特征 |

---

## 8. 决策备忘

| 问题 | 建议 |
|------|------|
| 要不要上全链路 LLM 精排？ | **否**（实时 feed）；LLM 做 **离线索引与解释** |
| FM / Wide&Deep 还要学吗？ | **要**；精排仍是主力，和向量召回组合 |
| 生成式推荐何时上？ | 有 **百万级行为 + serving 预算** 后再做小流量 |
| 最小实时闭环？ | **Embedding 召回 + LightGBM + Redis 行为 + 曝光日志** |

---

## 9. 链接速查（复制用）

```text
综述
  https://aclanthology.org/2024.lrec-main.886.pdf
  https://arxiv.org/html/2510.27157v2
  https://arxiv.org/pdf/2504.16420

基线
  https://arxiv.org/abs/1606.07792   Wide&Deep
  https://arxiv.org/abs/1703.04247   DeepFM
  https://arxiv.org/abs/1706.06978   DIN
  https://arxiv.org/abs/1808.09781   SASRec

工业生成式
  https://arxiv.org/abs/2402.17152   HSTU
  https://arxiv.org/pdf/2602.22732     GR4AD

工程
  https://github.com/facebookresearch/faiss
  https://milvus.io/docs
  https://github.com/shenweichen/DeepCTR-Torch
  https://github.com/RUCAIBox/RecBole
  https://arxiv.org/abs/2209.07663   Monolith
```

---

*文档版本：2026-06-22 · 与 TenClip `news_feed` 模块对齐，随实现迭代可改 M1 任务勾选状态。*
