"""The PR review service: its own app ([apps.pr_review]), so a deploy gives it
its own pod. The web app awaits its def:protect functions; a call with no user
(the scheduled runner) carries JAC_BRIDGE_TOKEN and runs as `__bridge__`, so
nothing here reads or writes a workspace's graph."""

import time;

# What a review reports back. `retryable` tells the runner to try again later
# rather than fail the run (a GitHub 5xx, a model timeout).
obj ReviewOutcome {
    has ok: bool,
        verdict: str = "",
        summary: str = "",
        comments: int = 0,
        blocking: int = 0,
        review_url: str = "",
        error: str = "",
        retryable: bool = False;
}

# The service is up and answering; what the web app's status check calls.
def:protect review_ping -> dict[str, any] {
    return {
        "ok": True,
        "service": "pr_review",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    };
}

# Review one pull request at one commit. A stub until #281 reads the diff and
# asks the model: it answers a fixed comment-only review, so the runner (#280)
# can be built against the real call.
def:protect review_pr(
    repo: str,
    pr_number: int,
    head_sha: str,
    instructions: str = "",
    mode: str = "comment",
    model: str = ""
) -> ReviewOutcome {
    return ReviewOutcome(
        ok=True, verdict="comment", summary="No review yet: the reviewer is a stub."
    );
}
