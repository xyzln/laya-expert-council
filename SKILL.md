---
name: laya-expert-council
version: 1.0.0
author: xyzln
description: >-
  「决策中枢 + 5 领域专家」专家团，复刻 Laya 的 System-1 决策协议（零依赖、零联网），
  并作为 WorkBuddy 原生安全网关：PreToolUse 钩子在 Bash/Write/Edit/WebFetch 执行前做风险判定，
  灾难性指令拦截(deny)、高危转人工(ask)。专家覆盖安全合规、代码评审、运维SRE、需求分诊、测试质量，
  对固定题型给出校准式置信度，低置信自动弃权升级。
metadata:
  type: skill
  category: 安全与效率
  triggers:
    - 决策
    - 风险评估
    - 命令风险
    - 该不该执行
    - 高危操作
    - 兜底拦截
    - 专家评审
    - 代码评审
    - 运维风险
    - 需求分诊
  allowed-tools:
    - Bash
    - Read
    - Write
---

# Laya决策专家团（WorkBuddy 原生安全网关 + 5 专家）

本 skill 以**专家团**形式运行：一个**决策中枢**协调 **5 个领域专家**，并自带一道 **WorkBuddy 原生安全网关**。
全部**零外部依赖、零联网、不装任何模型权重**——加载本 skill 的大模型本身就是决策引擎。

> 原理：复刻 Convai 的 Laya「System-1 决策模型」的三条核心——
> ① 固定答案空间的**结构化决策瓶颈**(choice/score/noul)；② **校准式置信度 + 弃权闸门**；
> ③ **预测与行动分离**（高危闸门强制人工确认）。原版需联网下载 300M+ 权重并装 torch，本版让大模型自己当引擎。

## 专家团组成

| 专家 | 负责维度 | 高危闸门 |
|---|---|---|
| `expert-security-compliance` | 数据分级 / PII / 出网 / 审批 | requires_approval |
| `expert-code-reviewer` | 改动类型 / 破坏性 / 测试覆盖 | breaking, needs_human_review |
| `expert-ops-sre` | 破坏性 / 提权 / 爆炸半径 / 回滚 | destructive, privileged, requires_confirmation |
| `expert-product-triage` | 意图 / 紧急度 / 归属 / 是否需人工 | needs_human |
| `expert-quality-gate` | 通过失败 / 严重度 / 发布阻塞 | blocks_release |

## PreToolUse 安全网关（核心差异点）

勾子 `hooks/hook_gate.py` 在 WorkBuddy 每次执行工具前调用，输出 `allow | ask | deny`：

- **deny（硬拦截）**：灾难性黑名单 —— `rm -rf /`、`git push --force`、`curl … | sh`、fork-bomb 等。
- **ask（转人工确认）**：提权（`sudo`/`su`）、写敏感路径（`.env`/`id_rsa`/`/etc`/`.git`/`.codebuddy`）、或引擎判出任一高危闸门。
- **allow**：未命中风险模式（`ls`/`grep`/写普通代码均放行）。
- **fail-safe**：引擎异常时默认转 `ask`，绝不静默放行。

> 引擎判定只升到 `ask`，真正的 `deny` 仅来自灾难性黑名单——正常命令不会被误伤。

## 四阶段工作流（专家团）

1. **路由 route** — `python3 scripts/laya_engine.py route --state '<文本>'` 选出最相关专家。
2. **出题 prompt** — `python3 scripts/laya_engine.py prompt --schema-file assets/schemas/<x>.json --state '<文本>'` 生成 System-1 决策提示词。
3. **作答** — 大模型按提示词输出 JSON：`{"<qid>": {"value": ..., "confidence": 0.0~1.0}}`。
4. **校准 / 闸门 / 共识 / 审计** — `validate`（归一化+`min_confidence`闸门）→ `consensus`（多专家融合）→ `audit`（JSONL 留痕）。

## 安装与部署

```bash
python3 scripts/install.py                 # 软链 skill + 合并 PreToolUse 钩子（用户级，重启 WorkBuddy 生效）
python3 scripts/install.py --scope project  # 项目级（写入 .codebuddy/settings.json，便于团队共享）
python3 scripts/install.py --uninstall      # 卸载
```

## 诚实的边界

- 置信度是**大模型自我报告**（非 RLCD 真·校准）。生产建议 `min_confidence` 设 0.6~0.7，高 stakes 操作一律走高闸门，**不自动执行**。
- 勾子里跑的是**离线条目**（关键词/CJK 二元组 + 黑名单），是兜底 baseline；真实决策能力来自加载本 skill 的 LLM。
- 详细原理与协议见 `references/`：`principle.md`、`engine.md`、`calibration.md`、`expert-team.md`、`question-library.md`、`hooks.md`。

## 发布

- GitHub：https://github.com/xyzln/laya-expert-council
- SkillHub：本包已含 `icon.png`(512×512) + `skillhub.json` 元信息，运行 `python3 scripts/publish.py` 生成上传 zip，到 https://skillhub.cn 提交审核即可上架。
