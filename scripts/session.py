#!/usr/bin/env python3
"""
muse-image session 管理（轻量单文件状态）。

会话状态写在 .gpt-image-gen/sessions/<id>.json。
没有 journal、没有 snapshot、没有 lease——agent 崩了最多丢"当前未提交那一答"。

子命令:
  new                          创建新 session，输出 id
  show [--id ID]               打印当前/指定 session 状态
  set --id ID --field K --value V[或 --json '{"k":"v"}']
  next-phase --id ID           推进 phase 到下一阶段
  add-version --id ID --prompt-file PATH --image PATH
  list                         列出所有 session 概要

phase 状态机:
  new → q1..q8 → synthesizing → dry_run → generating → reviewing → (refine|accept|restart)
  refine → q* (重提改动轴) → synthesizing → ...
  accept → completed
"""
import argparse, json, os, sys, datetime, glob

ROOT = os.environ.get("GPT_IMAGE_GEN_ROOT") or os.getcwd()
SESS_DIR = os.path.join(ROOT, ".muse-image", "sessions")

# 8 轴 brief schema（顺序 = 默认询问顺序）
BRIEF_FIELDS = [
    "use_case",          # q1 使用场景
    "audience",          # q2 目标用户
    "content_seed",      # q3 用户原始一句话(深挖前)
    "content",           # q3 内容(深挖后拼成的中文可读总览)
    "content_sections",  # q3 深挖出的分维度字典(详见 SKILL §3.3)
    "effect",            # q4 展示效果（数组）
    "style_id",          # q5 风格 ID（或 freeform 复合）
    "suppression",       # q6 用户抑制(字符串 或 字符串列表)
    "reference_image",   # q7 参考图路径 + Claude 提取的描述
    "aspect_ratio",      # q8 比例(可自定义 W:H)
]

PHASE_ORDER = [
    "new",
    "q1_use_case", "q2_audience", "q3_content", "q4_effect",
    "q5_style", "q6_suppression", "q7_reference", "q8_aspect",
    "synthesizing", "dry_run", "generating", "reviewing",
    "completed",
]


def _ensure_dir():
    os.makedirs(SESS_DIR, exist_ok=True)


def _path(sid):
    return os.path.join(SESS_DIR, f"{sid}.json")


def _load(sid):
    p = _path(sid)
    if not os.path.exists(p):
        print(f"session not found: {sid}", file=sys.stderr)
        sys.exit(1)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(state):
    state["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(_path(state["id"]), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def cmd_new(_args):
    _ensure_dir()
    sid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    state = {
        "id": sid,
        "phase": "new",
        "brief": {k: None for k in BRIEF_FIELDS},
        "versions": [],          # [{n, prompt_file, image, accepted}]
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "updated_at": None,
    }
    _save(state)
    print(json.dumps({"ok": True, "id": sid, "path": _path(sid)}, ensure_ascii=False))


def cmd_show(args):
    sid = args.id or _latest_id()
    if not sid:
        print(json.dumps({"ok": False, "error": "no sessions"}, ensure_ascii=False))
        return
    state = _load(sid)
    print(json.dumps(state, ensure_ascii=False, indent=2))


def cmd_set(args):
    state = _load(args.id)
    if args.field and args.json:
        # --field X --json '<value-json>' → value can be list/dict/str/number
        val = json.loads(args.json)
        if args.field in BRIEF_FIELDS:
            state["brief"][args.field] = val
        else:
            state[args.field] = val
    elif args.json:
        patch = json.loads(args.json)
        if not isinstance(patch, dict):
            print("--json without --field must be a JSON object (dict patch). "
                  "Use --field X --json '<value>' to set a single field to a list/etc.",
                  file=sys.stderr)
            sys.exit(1)
        for k, v in patch.items():
            if k in BRIEF_FIELDS:
                state["brief"][k] = v
            else:
                state[k] = v
    elif args.field:
        if args.field in BRIEF_FIELDS:
            state["brief"][args.field] = args.value
        else:
            state[args.field] = args.value
    else:
        print("need --field or --json", file=sys.stderr)
        sys.exit(1)
    _save(state)
    print(json.dumps({"ok": True, "phase": state["phase"]}, ensure_ascii=False))


def cmd_merge(args):
    """Merge a JSON dict patch into a dict-valued field (e.g. content_sections)."""
    state = _load(args.id)
    patch = json.loads(args.json)
    if not isinstance(patch, dict):
        print("merge --json must be a JSON object", file=sys.stderr)
        sys.exit(1)
    container = state["brief"] if args.field in BRIEF_FIELDS else state
    cur = container.get(args.field) or {}
    if not isinstance(cur, dict):
        print(f"field {args.field} is not a dict, cannot merge", file=sys.stderr)
        sys.exit(1)
    cur.update(patch)
    container[args.field] = cur
    _save(state)
    print(json.dumps({"ok": True, "phase": state["phase"], "field": args.field, "keys": list(cur.keys())}, ensure_ascii=False))


def cmd_next_phase(args):
    state = _load(args.id)
    cur = state["phase"]
    try:
        idx = PHASE_ORDER.index(cur)
    except ValueError:
        print(f"unknown phase: {cur}", file=sys.stderr)
        sys.exit(1)
    if idx + 1 >= len(PHASE_ORDER):
        state["phase"] = "completed"
    else:
        state["phase"] = args.to or PHASE_ORDER[idx + 1]
    _save(state)
    print(json.dumps({"ok": True, "phase": state["phase"]}, ensure_ascii=False))


def cmd_add_version(args):
    state = _load(args.id)
    n = len(state["versions"]) + 1
    state["versions"].append({
        "n": n,
        "prompt_file": args.prompt_file,
        "image": args.image,
        "accepted": False,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    _save(state)
    print(json.dumps({"ok": True, "n": n}, ensure_ascii=False))


def cmd_accept(args):
    state = _load(args.id)
    if not state["versions"]:
        print("no versions yet", file=sys.stderr); sys.exit(1)
    state["versions"][-1]["accepted"] = True
    state["phase"] = "completed"
    _save(state)
    print(json.dumps({"ok": True, "final": state["versions"][-1]}, ensure_ascii=False))


def cmd_list(_args):
    _ensure_dir()
    out = []
    for p in sorted(glob.glob(os.path.join(SESS_DIR, "*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            s = json.load(f)
        out.append({
            "id": s["id"], "phase": s["phase"],
            "versions": len(s.get("versions", [])),
            "updated_at": s.get("updated_at"),
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _latest_id():
    _ensure_dir()
    files = sorted(glob.glob(os.path.join(SESS_DIR, "*.json")))
    if not files:
        return None
    return os.path.splitext(os.path.basename(files[-1]))[0]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("new")

    s = sub.add_parser("show"); s.add_argument("--id")
    s = sub.add_parser("set")
    s.add_argument("--id", required=True)
    s.add_argument("--field"); s.add_argument("--value")
    s.add_argument("--json", help="patch via JSON object")

    s = sub.add_parser("merge")
    s.add_argument("--id", required=True)
    s.add_argument("--field", required=True)
    s.add_argument("--json", required=True, help="JSON dict to merge into the field")

    s = sub.add_parser("next-phase")
    s.add_argument("--id", required=True); s.add_argument("--to")

    s = sub.add_parser("add-version")
    s.add_argument("--id", required=True)
    s.add_argument("--prompt-file", required=True)
    s.add_argument("--image", required=True)

    s = sub.add_parser("accept"); s.add_argument("--id", required=True)
    sub.add_parser("list")

    args = ap.parse_args()
    {
        "new": cmd_new, "show": cmd_show, "set": cmd_set, "merge": cmd_merge,
        "next-phase": cmd_next_phase, "add-version": cmd_add_version,
        "accept": cmd_accept, "list": cmd_list,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
