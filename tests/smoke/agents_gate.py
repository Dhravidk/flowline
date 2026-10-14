#!/usr/bin/env python3
"""Smoke test for AI responsibilities against a running server and
github_stub.py: a move onto a role's step queues the role's responsibilities
(once per task while one is active), the AI switch, a missing PR and a
switched-off responsibility each skip with a log line, and another workspace
sees none of it. Reuses webhook_gate's helpers.
Usage: agents_gate.py [base_url] [stub_url]"""
import json
import sys

import webhook_gate as wg
from webhook_gate import check, walker, project, req

REPO = "ci-org/agents-repo"


def reports(name, body=None):
    status, raw = req(wg.BASE, "POST", f"/walker/{name}", body or {})
    try:
        data = json.loads(raw).get("data") or {}
    except ValueError:
        return []
    return data.get("reports") or []


def runs(task_id):
    rep = reports("ListRuns", {"task_id": task_id})
    return rep[0] if rep and isinstance(rep[0], list) else []


def task_log(task_id):
    pg = walker("ListLogEntries", {"from_date": "2020-01-01", "to_date": "2030-12-31",
                                   "task_id": task_id, "page_size": 100})
    return [r.get("activity", "") for r in pg.get("rows", [])]


def update(t, **changes):
    """UpdateTask overwrites every field, so a save carries the task's own."""
    body = {k: t.get(k, "") for k in ("title", "category", "priority", "status", "step_id",
                                      "due_date", "start_date", "notes", "issue_link",
                                      "pr_link", "reviewer_id", "review_due", "project_id")}
    body.update({"task_id": t["id"], "tags": t.get("tags", []), "estimate": t.get("estimate", 0.0),
                 "assignee_ids": t.get("assignee_ids", [])})
    body.update(changes)
    return walker("UpdateTask", body)


def move(task_id, step_id):
    return walker("MoveTask", {"task_id": task_id, "step_id": step_id})


def queue_suite():
    wg.login("agents")
    pid = project()
    role = walker("SaveRole", {"name": "Product Engineer"}).get("role", {})
    walker("SaveRole", {"name": "Developer"})
    building = walker("SaveStep", {"name": "Building", "kind": "active", "owner": "Developer"})
    review = walker("SaveStep", {"name": "In review", "kind": "handoff", "owner": "Product Engineer"})
    bid, rid = building.get("id", ""), review.get("id", "")
    check("a role and the two steps", bool(role.get("id") and bid and rid), (role, building, review))
    saved = walker("SaveResponsibility", {"role_id": role["id"], "on_steps": [rid]})
    resp_id = (saved.get("responsibility") or {}).get("id", "")
    check("code review on In review", saved.get("ok") is True, saved)

    made = walker("CreateTask", {"title": "Add rate limits", "project_id": pid, "step_id": bid})
    t = update(made, pr_link=f"https://github.com/{REPO}/pull/7")
    tid = t.get("id", "")
    check("a task on Building with a linked PR", t.get("pr_link", "").endswith("/pull/7"), t)

    move(tid, rid)
    check("with AI off, a move queues nothing", runs(tid) == [], runs(tid))
    check("  and the move's log line says AI is off",
          any("AI code review skipped: AI is off" in a for a in task_log(tid)), task_log(tid))

    move(tid, bid)
    walker("SetAiEnabled", {"enabled": True})
    move(tid, rid)
    queued = runs(tid)
    first = queued[0] if queued else {}
    check("with AI on, the move queues one run", len(queued) == 1 and first.get("status") == "queued"
          and first.get("key") == "code_review" and first.get("responsibility_id") == resp_id, queued)
    check("  carrying the PR from the link", first.get("pr_repo") == REPO and first.get("pr_number") == 7, first)
    check("  and the log line names it", any("Queued AI code review" in a for a in task_log(tid)), task_log(tid))

    move(tid, bid)
    move(tid, rid)
    check("a second landing while one is active queues nothing more", len(runs(tid)) == 1, runs(tid))

    plain = walker("CreateTask", {"title": "No PR yet", "project_id": pid, "step_id": bid})
    move(plain["id"], rid)
    check("a task with no PR is skipped", runs(plain["id"]) == []
          and any("skipped: no linked pull request" in a for a in task_log(plain["id"])), task_log(plain["id"]))

    off = walker("CreateTask", {"title": "Responsibility off", "project_id": pid, "step_id": bid})
    off = update(off, pr_link=f"https://github.com/{REPO}/pull/8")
    walker("SaveResponsibility", {"responsibility_id": resp_id, "enabled": False, "on_steps": [rid]})
    move(off["id"], rid)
    check("a switched-off responsibility queues nothing", runs(off["id"]) == [], runs(off["id"]))
    walker("SaveResponsibility", {"responsibility_id": resp_id, "enabled": True, "on_steps": [rid]})

    other = walker("CreateTask", {"title": "Somewhere else", "project_id": pid, "step_id": rid})
    other = update(other, pr_link=f"https://github.com/{REPO}/pull/9")
    move(other["id"], bid)
    check("a step the responsibility is not on queues nothing", runs(other["id"]) == [], runs(other["id"]))

    home = wg.TOKEN
    wg.login("agents-b")
    check("another workspace sees none of the runs", runs(tid) == [], runs(tid))
    wg.TOKEN = home
    return tid


def main() -> int:
    if not check("server ready within timeout", wg.wait_ready()):
        return 2
    queue_suite()
    print("agents gate: " + ("PASS" if not wg.FAILS else f"FAIL ({len(wg.FAILS)})"))
    return 1 if wg.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
