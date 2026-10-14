#!/usr/bin/env python3
"""Smoke test for AI responsibilities against a running server and
github_stub.py: a move onto a role's step queues the role's responsibilities
(once per task while one is active), the AI switch, a missing PR and a
switched-off responsibility each skip with a log line, another workspace sees
none of it, and the scheduled runner reviews a queued run (FLOWLINE_FAKE_LLM),
retries a 5xx, fails a 403, skips a closed PR and a commit already reviewed,
and takes a run back whose claim lapsed. Reuses webhook_gate's helpers.
Usage: agents_gate.py [base_url] [stub_url]"""
import json
import sys
import time

import webhook_gate as wg
from webhook_gate import check, walker, project, req, connect

REPO = "ci-org/agents-repo"
INST = 4747
SETTLED = ("done", "failed", "skipped", "cancelled")


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


def settle(task_id, want=1, timeout=90):
    """Wait for the task's newest `want` runs to finish; the runner ticks
    every FLOWLINE_AI_INTERVAL_SECONDS."""
    deadline = time.time() + timeout
    rows = runs(task_id)
    while time.time() < deadline:
        rows = runs(task_id)
        if len(rows) >= want and all(r.get("status") in SETTLED for r in rows[:want]):
            return rows
        time.sleep(2)
    return rows


def stub(path, body):
    status, _ = req(wg.STUB, "POST", path, body, auth=False)
    return status == 200


def pull(number, head, state="open"):
    return {"repo": REPO, "number": number, "head_sha": head, "state": state}


def runner_suite():
    stub("/_stub/reset", {"installations": [INST], "repos": {REPO: []}})
    stub("/_stub/pulls", {"pulls": [pull(7, "sha-7a"), pull(8, "sha-8"), pull(9, "sha-9"),
                                    pull(10, "sha-10", "closed"), pull(11, "sha-11")]})
    wg.login("runner")
    check("runner: connect GitHub", connect(INST).get("ok"))
    pid = project()
    role = walker("SaveRole", {"name": "Product Engineer"}).get("role", {})
    walker("SaveRole", {"name": "Developer"})
    bid = walker("SaveStep", {"name": "Building", "kind": "active", "owner": "Developer"}).get("id", "")
    rid = walker("SaveStep", {"name": "In review", "kind": "handoff", "owner": "Product Engineer"}).get("id", "")
    walker("SaveResponsibility", {"role_id": role["id"], "on_steps": [rid], "instructions": "Check errors."})
    walker("SetAiEnabled", {"enabled": True})

    def landed(title, number):
        t = walker("CreateTask", {"title": title, "project_id": pid, "step_id": bid})
        t = update(t, pr_link=f"https://github.com/{REPO}/pull/{number}")
        move(t["id"], rid)
        return t["id"]

    a = landed("Reviewed once", 7)
    done = settle(a)
    first = done[0] if done else {}
    check("runner: a queued run is reviewed", first.get("status") == "done" and first.get("verdict") == "comment"
          and first.get("head_sha") == "sha-7a" and first.get("model") == "fake", done)
    check("  and the task's log says so", any("AI code review · 0 comments, 0 blocking" in x for x in task_log(a)),
          task_log(a))
    calls = [c[1] for c in wg.stub_calls(INST)]
    check("  reading the PR with the installation's token", f"/repos/{REPO}/pulls/7" in calls, calls)
    move(a, bid)
    move(a, rid)
    again = settle(a, 2)
    check("runner: the same commit is not reviewed twice", len(again) == 2 and again[0].get("status") == "skipped"
          and "already reviewed" in again[0].get("error", ""), again)

    stub("/_stub/fault", {"method": "GET", "path": f"/repos/{REPO}/pulls/8", "status": 502, "times": 1})
    b = landed("Retried after a 5xx", 8)
    retried = settle(b, 1, 120)
    check("runner: a GitHub 5xx is retried, then succeeds", retried and retried[0].get("status") == "done"
          and retried[0].get("attempts") == 2, retried)

    stub("/_stub/fault", {"method": "GET", "path": f"/repos/{REPO}/pulls/9", "status": 403, "times": 5})
    c = landed("Refused with a 403", 9)
    refused = settle(c)
    check("runner: a 403 fails at once", refused and refused[0].get("status") == "failed"
          and refused[0].get("attempts") == 1 and "403" in refused[0].get("error", ""), refused)
    check("  and the task's log says why", any("AI code review failed" in x for x in task_log(c)), task_log(c))

    d = landed("Closed PR", 10)
    closed = settle(d)
    check("runner: a closed PR is skipped", closed and closed[0].get("status") == "skipped"
          and "closed" in closed[0].get("error", ""), closed)

    patch = "@@ -1,3 +1,5 @@\n import os\n+x = compute()  # BUG: wrong unit\n def f():\n+    pass  # TODO handle errors\n     return 1"
    stub("/_stub/pulls", {"pulls": [dict(pull(12, "sha-12"), files=[
        {"filename": "app/service.py", "status": "modified", "additions": 2, "deletions": 0, "patch": patch},
        {"filename": "package-lock.json", "status": "modified", "additions": 900, "deletions": 3, "patch": "@@ -1 +1 @@\n-a\n+b"},
        {"filename": "old.py", "status": "removed", "additions": 0, "deletions": 10, "patch": "@@ -1 +0,0 @@\n-x"},
        {"filename": "logo.png", "status": "added", "additions": 0, "deletions": 0},
    ])]})
    f = landed("Findings on added lines", 12)
    found = settle(f)
    row = found[0] if found else {}
    check("engine: findings land on added lines, lock, removed and binary files skipped",
          row.get("status") == "done" and row.get("comments") == 2 and row.get("blocking") == 1
          and row.get("verdict") == "request_changes", row)
    check("  and the task's log counts them", any("2 comments, 1 blocking" in x for x in task_log(f)), task_log(f))
    files = [c[1] for c in wg.stub_calls(INST) if c[1].endswith("/pulls/12/files")]
    check("  reading the PR's files once", len(files) == 1, files)
    posted = [r for r in wg.stub_state().get("reviews", []) if r["number"] == 12]
    review = posted[0] if posted else {}
    check("post: one review on the PR's head commit, inline comments on the added lines",
          len(posted) == 1 and review.get("commit_id") == "sha-12" and review.get("event") == "COMMENT"
          and sorted((c["path"], c["line"]) for c in review.get("comments", [])) == [("app/service.py", 2), ("app/service.py", 4)]
          and "AI code review" in (review.get("body") or ""), posted)
    check("  and the run links to it", "pullrequestreview-" in row.get("review_url", ""), row)

    def with_bug(number):
        return dict(pull(number, f"sha-{number}"), files=[
            {"filename": "app/a.py", "status": "modified", "additions": 1, "deletions": 0,
             "patch": "@@ -1,1 +1,2 @@\n a = 1\n+b = a / 0  # BUG"}])

    stub("/_stub/pulls", {"pulls": [with_bug(13), with_bug(14)]})
    stub("/_stub/fault", {"method": "POST", "path": f"/repos/{REPO}/pulls/13/reviews", "status": 403, "times": 5})
    g = landed("App lacks PR write", 13)
    lacking = settle(g)
    check("post: a 403 fails at once with the approval hint", lacking and lacking[0].get("status") == "failed"
          and "Pull requests: read and write" in lacking[0].get("error", ""), lacking)
    stub("/_stub/fault", {"method": "POST", "path": f"/repos/{REPO}/pulls/14/reviews", "status": 422, "times": 1})
    h = landed("A comment GitHub refuses", 14)
    fallback = settle(h)
    later = [r for r in wg.stub_state().get("reviews", []) if r["number"] == 14]
    check("post: a refused comment line falls back to the findings in the body",
          fallback and fallback[0].get("status") == "done" and len(later) == 1 and later[0]["comments"] == []
          and "app/a.py:2" in (later[0].get("body") or ""), later)

    stub("/_stub/fault", {"method": "GET", "path": f"/repos/{REPO}/pulls/11", "times": 1, "delay": 20})
    e = landed("Claim lapsed", 11)
    lapsed = settle(e, 1, 150)
    check("runner: a run whose claim lapsed is taken back and finished once",
          lapsed and lapsed[0].get("status") == "done" and lapsed[0].get("attempts") == 2, lapsed)



def main() -> int:
    if not check("server ready within timeout", wg.wait_ready()):
        return 2
    unconnected = queue_suite()
    queued_home = wg.TOKEN
    runner_suite()
    wg.TOKEN = queued_home
    gone = settle(unconnected)
    check("runner: a workspace with no GitHub connection fails its run",
          gone and gone[0].get("status") == "failed" and "not connected" in gone[0].get("error", ""), gone)
    print("agents gate: " + ("PASS" if not wg.FAILS else f"FAIL ({len(wg.FAILS)})"))
    return 1 if wg.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
