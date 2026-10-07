#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook_gate.py - WorkBuddy PreToolUse 决策闸门（Laya System-1 安全网关）。

WorkBuddy 在任意工具（Bash/Write/Edit/WebFetch...）执行前，会把工具信息通过
stdin 以 JSON 形式喂给本脚本。本脚本据此做一次 *快速、离线的* 风险判定：
  1. 硬黑名单：命中灾难性指令（rm -rf /、mkfs、git push --force...）直接 deny；
  2. Laya 引擎离线路径：用 command-risk / write-risk 题型结构化判定；
  3. 高危闸门（destructive/privileged/...）升级为 deny 或 ask；
  4. 引擎异常时 fail-safe -> 转 ask（需人工确认），绝不静默放行。

决策结果以 WorkBuddy 规范的 stdout JSON 返回：
  {"hookSpecificOutput": {"hookEventName":"PreToolUse",
                          "permissionDecision":"allow|ask|deny",
                          "permissionDecisionReason":"..."}}
并写入审计日志（默认 ~/.cache/laya-decision/hook_audit.jsonl）。

零外部依赖：仅标准库 + 同仓 scripts/laya_engine.py。无联网、无调用大模型。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import laya_engine as le  # noqa: E402

MIN_CONF = 0.5

# --------------------------------------------------------------------------- #
# 致命指令硬黑名单（直接 deny，绕开引擎质量）
# --------------------------------------------------------------------------- #
CATASTROPHIC = [
    "rm -rf /", "rm -rf ~", "rm -rf /*", "rm -fr /", "rm -rf ./*",  # 注意 ./* 也拦
    "mkfs", "dd if=", "dd if =",
    "shutdown", "reboot", "poweroff", "halt",
    "git push --force", "git push -f ", "git push --force-with-lease",
    "git reset --hard", "git clean -f", "git clean -fd",
    "chmod -R 777 /", "chmod 777 /", "chmod 000 /",
    "curl ", "wget ",  # 占位，下面用正则精确匹配管道到 shell
    "> /dev/sd", "> /dev/nvme", ":(){ :|:& };:",
]
_PIPE_SHELL = re.compile(r"(curl|wget)\s+\S+\s*\|\s*(sudo\s+)?(ba)?sh\b")
_FORK_BOMB = re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;:")

# 仅需人工确认的提权/危险（ask 而非 deny）
PRIVILEGED_HINTS = ("sudo ", "sudo\t", "su -", "doas ", "pkexec ")

# 写操作敏感路径（ask）
SENSITIVE_PATH = re.compile(
    r"(\.env|id_rsa|id_ed25519|\.pem|\.key|credentials|secrets|"
    r"/etc/|/usr/|/System/|/root/|/var/|/boot/|"
    r"\.git/|\.codebuddy/|known_hosts|authorized_keys)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# 判定辅助
# --------------------------------------------------------------------------- #
def _catastrophic(text: str) -> str | None:
    t = text.lower()
    if _FORK_BOMB.search(text) or _PIPE_SHELL.search(text):
        return "检测到管道下载即执行 / fork-bomb 类危险指令"
    for pat in CATASTROPHIC:
        if pat in t and pat not in ("curl ", "wget "):
            return "命中灾难性指令黑名单: %s" % pat.strip()
    return None


def _pick_schema_and_state(tool: str, inp: dict) -> tuple[str, str]:
    if tool == "Bash":
        return "command-risk", str(inp.get("command", ""))
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(inp.get("file_path", ""))
        body = str(inp.get("content") or inp.get("new_string") or
                   inp.get("old_string") or "")
        return "write-risk", "%s\n%s" % (path, body)
    # 其余工具：序列化输入，复用通用风险题型做粗筛
    return "command-risk", json.dumps(inp, ensure_ascii=False)


def _decide(tool: str, inp: dict) -> dict:
    """跑 Laya 引擎离线路径，仅把「明确为 True」的风险字段升级为 ask。

    设计原则：引擎信号只升到 ask（人工确认），真正的硬拦截（deny）只来自
    _catastrophic 灾难性黑名单，避免把「无信号」或「sudo」误判成致命拦截。
    """
    schema_id, state = _pick_schema_and_state(tool, inp)
    schema_file = os.path.join(ROOT, "assets", "schemas", schema_id + ".json")
    result = {"severity": "allow", "reasons": []}
    try:
        sk, questions = le.load_schema(schema_file)
        payload = le.run_decide(state, sk, questions, None, MIN_CONF,
                                "hook-heuristic")
        for qid, ans in payload["decision"].items():
            if ans.get("value") is True:
                result["severity"] = _max_sev(result["severity"], "ask")
                is_watch = any(k in qid.lower() for k in le.WATCH_KEYWORDS)
                result["reasons"].append("Laya %s=%s（%s）" % (
                    qid, True, "高危闸门" if is_watch else "风险字段"))
    except Exception as exc:  # fail-safe：异常不静默放行
        result["severity"] = _max_sev(result["severity"], "ask")
        result["reasons"].append("决策引擎异常(%s)，已转人工确认" % type(exc).__name__)
    return result


_SEV_ORDER = {"allow": 0, "ask": 1, "deny": 2}


def _max_sev(a: str, b: str) -> str:
    return a if _SEV_ORDER[a] >= _SEV_ORDER[b] else b


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        _emit("ask", "无法解析 hook 输入 JSON，已转人工确认")
        return 0

    tool = str(data.get("tool_name", ""))
    inp = data.get("tool_input") or {}
    state = ""
    reasons: list[str] = []

    sev = "allow"

    # 1) Bash 灾难性黑名单
    if tool == "Bash":
        cmd = str(inp.get("command", ""))
        state = cmd
        hit = _catastrophic(cmd)
        if hit:
            sev = "deny"
            reasons.append(hit)
        if sev != "deny":
            for h in PRIVILEGED_HINTS:
                if h in cmd.lower():
                    sev = _max_sev(sev, "ask")
                    reasons.append("检测到提权指令(%s)，需人工确认" % h.strip())
                    break

    # 2) Write/Edit 敏感路径
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(inp.get("file_path", ""))
        state = path
        if SENSITIVE_PATH.search(path):
            sev = _max_sev(sev, "ask")
            reasons.append("写入敏感路径(%s)，需人工确认" % path)

    # 3) Laya 引擎结构化判定
    eng = _decide(tool, inp)
    sev = _max_sev(sev, eng["severity"])
    reasons.extend(eng["reasons"])

    # 合并决策
    if sev == "allow" and not reasons:
        decision, why = "allow", "Laya 网关：未命中风险模式，放行"
    elif sev == "allow":
        decision, why = "allow", "Laya 网关：放行（备注: %s）" % "; ".join(reasons)
    elif sev == "ask":
        decision, why = "ask", "Laya 网关需确认: " + "; ".join(reasons)
    else:
        decision, why = "deny", "Laya 网关已拦截: " + "; ".join(reasons)

    _audit(data, tool, state, decision, why)
    _emit(decision, why)
    return 0


def _emit(decision: str, reason: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    if decision == "deny":
        out["continue"] = False
    else:
        out["continue"] = True
    print(json.dumps(out, ensure_ascii=False))


def _audit(data: dict, tool: str, state: str, decision: str, why: str) -> None:
    try:
        adir = os.environ.get("LAYA_AUDIT_DIR") or os.path.join(
            os.path.expanduser("~"), ".cache", "laya-decision")
        os.makedirs(adir, exist_ok=True)
        rec = {
            "source": "hook", "tool": tool, "state": state[:500],
            "decision": decision, "reason": why,
            "session_id": data.get("session_id"),
            "cwd": data.get("cwd"),
        }
        with open(os.path.join(adir, "hook_audit.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
