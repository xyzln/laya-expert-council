# Laya决策专家团 · laya-expert-council

把 **Laya 的 System-1 决策协议**复刻成一个 **WorkBuddy 原生专家团**：一个能自己跑起来的安全决策网关 +
「决策中枢 + 5 领域专家」。零外部依赖、零联网、不装任何模型权重——加载本项目的 WorkBuddy 大模型本身就是决策引擎。

> 作者：[@xyzln](https://github.com/xyzln) ｜ 已发布到 [GitHub](https://github.com/xyzln/laya-expert-council) 与 SkillHub。

---

## 它能做什么

- **工具执行前拦截（安全网关）**：`Bash` / `Write` / `Edit` / `WebFetch` 跑之前，PreToolUse 勾子先做一次离线风险判定。
  - 灾难性指令（`rm -rf /`、`git push --force`、`curl … | sh`、fork-bomb…）→ **直接拦截 (deny)**
  - 提权 / 写敏感文件（`.env`、`id_rsa`、`/etc`、`.git`、`.codebuddy`…）→ **转人工确认 (ask)**
  - 正常命令（`ls`、`grep`、写 `src/app.py`）→ 放行
- **专家团决策协议**：`决策中枢 + 5 领域专家`（安全合规 / 代码评审 / 运维 SRE / 需求分诊 / 测试质量），
  针对固定题型 `choice/score/noul` 作答并给出校准式置信度，低置信自动弃权升级。
- **审计留痕**：每次闸门判定写入 `hook_audit.jsonl`，可回溯升级率/弃权率。

## 快速开始（本地安装）

```bash
# 1. 克隆
git clone https://github.com/xyzln/laya-expert-council.git
cd laya-expert-council

# 2. 部署：软链 skill + 合并 PreToolUse 钩子到用户级 settings
python3 scripts/install.py

# 3. 重启 WorkBuddy —— 之后每次危险操作都会被网关拦一道

# 4. 自测
python3 tests/test_hook.py               # 10 个闸门用例
python3 scripts/laya_engine.py selftest   # 引擎自检
```

项目级部署（写入仓库 `.codebuddy/settings.json`，便于团队共享）：
```bash
python3 scripts/install.py --scope project
```

## 发布到 SkillHub（让大家在 WorkBuddy 里搜到安装）

本仓库已按 SkillHub 规范备齐上架材料（`icon.png` 512×512 + `skillhub.json` 元信息）。

```bash
# 1. 校验发布材料是否齐全
python3 scripts/publish.py --check

# 2. 打包成上传 zip
python3 scripts/publish.py               # 生成 laya-expert-council-skillhub.zip
```

然后在浏览器完成上架（需你的 SkillHub 开发者账号）：
1. 访问 **https://skillhub.cn** → 右上角「发布团队 skill」
2. 选择发布类型（免费版即可）
3. 上传 `laya-expert-council-skillhub.zip`，并确认元信息（名称/描述/分类/权限已写入 `skillhub.json`，可直接照填）
4. 提交 → 平台安全审核（1–3 个工作日）→ 审核通过后于「技能列表」点「上架」
5. 之后所有 WorkBuddy 用户都能在技能入口搜索「Laya决策专家团」并一键安装

> 审核要点：本 skill **纯标准库、无联网、无恶意代码**，且 `deny` 仅针对灾难性黑名单、`ask` 仅针对高危确认，
> 不会静默拦截正常操作，合规性与稳定性无风险。

## 目录结构

```
laya-expert-council/
├── SKILL.md                     # 主 skill（专家团中枢 + 网关说明）
├── icon.png                     # 512×512 图标（SkillHub 要求）
├── skillhub.json                # SkillHub 上架元信息（名称/描述/分类/权限/标签）
├── hooks/hook_gate.py           # PreToolUse 安全闸门（核心差异点）
├── scripts/
│   ├── laya_engine.py           # 零依赖决策引擎：prompt/validate/decide/route/consensus/audit/selftest
│   ├── calibrate.py             # min_confidence 阈值扫描
│   ├── batch_eval.py            # 批量评估报表
│   ├── schema_gen.py            # 从自然语言生成 schema 草稿
│   ├── install.py               # 一键部署（skill 软链 + 钩子合并）
│   └── publish.py              # 打包 SkillHub 上传包
├── experts/                     # 5 领域专家（SKILL.md + schema.json）+ _registry.json
├── assets/schemas/              # 7 套现成题型
├── config/settings.hooks.json   # 钩子配置模板
├── references/                  # 原理 / 引擎 API / 校准 / 专家团 / 题型库 / 钩子接入
└── tests/                       # test_hook.py + samples.jsonl
```

## 设计取舍（诚实说明）

- 置信度是**大模型自我报告**（非 RLCD 真·校准）。生产建议 `min_confidence` 设 0.6~0.7，高 stakes 操作一律走高闸门，**不自动执行**。
- 勾子里跑的是**离线条目**（关键词/CJK 二元组 + 黑名单），是兜底 baseline；真实决策能力来自加载本项目的 LLM。
- 详细原理与协议见 [`references/`](references/)。

## License

MIT —— 自由用于个人与团队的安全决策网关集成。
