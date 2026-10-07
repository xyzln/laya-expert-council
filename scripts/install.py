#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py - 把 WorkBuddy-laya 部署进 WorkBuddy（skill 软链 + 钩子合并）。

用法：
  python3 scripts/install.py                 # 链接到 ~/.codebuddy/skills + 合并到用户级 settings
  python3 scripts/install.py --scope project # 合并到 当前目录/.codebuddy/settings.json（项目级）
  python3 scripts/install.py --mode copy     # 复制而非软链
  python3 scripts/install.py --uninstall     # 移除软链与钩子
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKILL_NAME = "laya-expert-council"
HOOK_REL = os.path.join("hooks", "hook_gate.py")


def _merge_hooks(settings: dict, hook_cmd: str) -> bool:
    """把本项目的 PreToolUse 钩子并入 settings，去重。返回是否发生变更。"""
    settings.setdefault("hooks", {})
    hooks = settings["hooks"]
    hooks.setdefault("PreToolUse", [])
    target = None
    for entry in hooks["PreToolUse"]:
        for h in entry.get("hooks", []):
            if h.get("command") == hook_cmd:
                target = entry
                break
    if target is not None:
        return False
    hooks["PreToolUse"].append({
        "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|WebFetch",
        "hooks": [{"type": "command", "command": hook_cmd, "timeout": 10}],
    })
    return True


def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def deploy(scope: str, mode: str) -> None:
    skills_dir = os.path.join(os.path.expanduser("~"), ".codebuddy", "skills")
    os.makedirs(skills_dir, exist_ok=True)
    dest = os.path.join(skills_dir, SKILL_NAME)

    # 1) 软链/复制 skill
    if os.path.islink(dest) or os.path.exists(dest):
        if os.path.islink(dest):
            os.unlink(dest)
        else:
            shutil.rmtree(dest)
    if mode == "link":
        os.symlink(ROOT, dest)
        print("已软链 skill -> %s" % dest)
    else:
        shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git"))
        print("已复制 skill -> %s" % dest)

    # 2) 合并钩子
    if scope == "project":
        target_settings = os.path.join(os.getcwd(), ".codebuddy", "settings.json")
    else:
        target_settings = os.path.join(os.path.expanduser("~"), ".codebuddy",
                                       "settings.json")

    hook_cmd = dest.replace(ROOT, ROOT)  # dest 已指向 ROOT（软链）或副本
    # 软链时 dest == ROOT；复制时 dest 是副本，钩子用副本路径
    hook_cmd = os.path.join(dest, HOOK_REL)

    settings = _read_json(target_settings)
    changed = _merge_hooks(settings, hook_cmd)
    if changed:
        _write_json(target_settings, settings)
        print("已合并 PreToolUse 钩子 -> %s" % target_settings)
    else:
        print("钩子已存在，无需变更: %s" % target_settings)


def uninstall() -> None:
    skills_dir = os.path.join(os.path.expanduser("~"), ".codebuddy", "skills")
    dest = os.path.join(skills_dir, SKILL_NAME)
    if os.path.islink(dest):
        os.unlink(dest)
        print("已移除软链: %s" % dest)
    elif os.path.isdir(dest):
        shutil.rmtree(dest)
        print("已移除目录: %s" % dest)
    # 清理钩子
    dest2 = os.path.join(os.getcwd(), ".codebuddy", "settings.json")
    for p in (dest2, os.path.join(os.path.expanduser("~"), ".codebuddy",
                                  "settings.json")):
        s = _read_json(p)
        pre = s.get("hooks", {}).get("PreToolUse", [])
        new_pre = []
        removed = False
        for entry in pre:
            kept = [h for h in entry.get("hooks", [])
                    if HOOK_REL.replace("\\", "/") not in h.get("command", "")]
            if len(kept) != len(entry.get("hooks", [])):
                removed = True
            if kept:
                new_pre.append({**entry, "hooks": kept})
        if removed:
            s.setdefault("hooks", {})["PreToolUse"] = new_pre
            if not s["hooks"]["PreToolUse"]:
                s["hooks"].pop("PreToolUse", None)
            if not s["hooks"]:
                s.pop("hooks", None)
            _write_json(p, s)
            print("已从 %s 移除钩子" % p)


def main() -> int:
    ap = argparse.ArgumentParser(description="部署 WorkBuddy-laya 到 WorkBuddy")
    ap.add_argument("--scope", choices=["user", "project"], default="user")
    ap.add_argument("--mode", choices=["link", "copy"], default="link")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()
    if args.uninstall:
        uninstall()
    else:
        deploy(args.scope, args.mode)
    print("\n完成。重启 WorkBuddy 后，PreToolUse 闸门即生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
