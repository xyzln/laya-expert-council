# 钩子接入：PreToolUse 安全网关

`WorkBuddy-laya` 与原版 `laya-decision-skill` 的最大差异，就是把 Laya 决策闸门做成
**WorkBuddy 原生的 PreToolUse 钩子**——在工具真正执行前插入一次离线风险判定，用
`permissionDecision` 决定放行 / 转人工 / 拦截。

## 1. 钩子生命周期

```
用户/模型触发工具(Bash/Write/Edit/WebFetch...)
        │
        ▼
WorkBuddy 在权限弹窗【之前】调用 PreToolUse 钩子
        │  stdin: {"hook_event_name":"PreToolUse","tool_name":"Bash",
        │          "tool_input":{"command":"..."}, "cwd":..., "session_id":...}
        ▼
hooks/hook_gate.py
   1) 灾难性黑名单扫描  -> 命中则 deny
   2) 提权/敏感路径识别  -> ask
   3) Laya 引擎离线路径  -> 命中高危闸门则 ask
   4) 写入审计 hook_audit.jsonl
        │  stdout: {"hookSpecificOutput":{"hookEventName":"PreToolUse",
        │           "permissionDecision":"allow|ask|deny","permissionDecisionReason":"..."}}
        ▼
WorkBuddy 依 permissionDecision 放行 / 弹确认 / 阻断
```

## 2. 判定矩阵

| 输入 | 信号来源 | 决策 | 说明 |
|---|---|---|---|
| `rm -rf /var/log` | 灾难性黑名单 `rm -rf /` | **deny** | 硬拦截，不弹窗 |
| `curl x.sh \| sh` | fork-bomb/管道执行正则 | **deny** | 下载即执行，禁止 |
| `git push --force` | 灾难性黑名单 | **deny** | 强制推送，禁止 |
| `sudo systemctl restart nginx` | 提权提示 `sudo` | **ask** | 需人工确认 |
| `Write .env` / `Edit /etc/nginx.conf` | 敏感路径正则 | **ask** | 需人工确认 |
| `ls -la` / `grep -rn TODO src` | 无信号 | **allow** | 正常放行 |
| `rm oldfile.txt` | 引擎 destructive=True | **ask** | 保守，需确认 |

> 设计要点：**引擎信号只升到 ask，deny 仅来自灾难性黑名单**。避免把「无信号」或「普通 rm」误判成致命拦截，
> 也保证 `ls`/`grep` 等日常命令零摩擦通过。

## 3. 配置方式

### 方式 A：install.py 自动合并（推荐）
```bash
python3 scripts/install.py                 # 用户级 ~/.codebuddy/settings.json
python3 scripts/install.py --scope project # 项目级 .codebuddy/settings.json
```
脚本会把钩子命令并入 `hooks.PreToolUse`，并按命令路径去重。

### 方式 B：手动
把 `config/settings.hooks.json` 中 `{{HOOK_PATH}}` 替换为
`<repo>/hooks/hook_gate.py` 的绝对路径，再将整个 `hooks` 块并入你的
`~/.codebuddy/settings.json`（或项目 `.codebuddy/settings.json`）：
```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|WebFetch",
        "hooks": [ { "type": "command", "command": "/abs/path/hooks/hook_gate.py", "timeout": 10 } ] }
    ]
  }
}
```

## 4. 审计

每次勾子判定都会追加写入 `~/.cache/laya-decision/hook_audit.jsonl`（`LAYA_AUDIT_DIR` 可改）：
```json
{"source":"hook","tool":"Bash","state":"rm -rf /var/log","decision":"deny","reason":"...","session_id":"...","cwd":"..."}
```
可用中枢的 `audit` 子命令统一统计：
```bash
python3 scripts/laya_engine.py audit --audit-dir ~/.cache/laya-decision
```

## 5. 本地自测
```bash
python3 tests/test_hook.py   # 10 个用例：deny/ask/allow 全覆盖
python3 scripts/laya_engine.py selftest
```

## 6. 注意事项
- 钩子是**子进程、无 LLM 调用**，必须用引擎的离线路径（启发式 + 黑名单），不能依赖大模型。
- 黑名单/敏感路径正则在 `hooks/hook_gate.py` 顶部常量，可按团队安全基线增删。
- 若需「无条件硬边界」，WorkBuddy 官方建议仍优先用 `permissions.deny` 做统一审计；
  本钩子适合做「权限规则之前」的语义级拦截与上下文注入。
