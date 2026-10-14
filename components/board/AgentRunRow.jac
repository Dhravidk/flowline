"""One AI run in the task sheet: what it is doing or found, the review on
GitHub, and Retry or Cancel when they apply."""

import from ...models { AgentRunView }
import from ..ui.button { Button }

glob STATUS_WORDS: dict[str, str] = {
         "queued": "Queued",
         "running": "Reviewing",
         "done": "Reviewed",
         "failed": "Failed",
         "skipped": "Skipped",
         "cancelled": "Cancelled"
     };

# The line under the status: the findings once done, else the run's reason.
def runLine(run: AgentRunView) -> str {
    if run.status == "done" {
        found = str(run.comments) + (" comment" if run.comments == 1 else " comments");
        if run.blocking > 0 {
            found = found + ", " + str(run.blocking) + " blocking";
        }
        return found;
    }
    if run.status == "queued" and run.attempts > 0 {
        return "Retrying: " + (run.error or "the last try failed.");
    }
    return run.error;
}

def:pub AgentRunRow(
    run: AgentRunView,
    name: str,
    busy: bool,
    onRetry: Callable[[str], None],
    onCancel: Callable[[str], None]
) -> JsxElement {
    line = runLine(run);
    live = run.status == "queued" or run.status == "running";
    again = run.status in ["failed", "skipped", "cancelled"];
    return
        <li
            className="grid gap-1 border-b py-2 text-[13px] leading-snug"
            data-run={run.status}
        >
            <div className="flex min-w-0 items-center gap-2">
                <span className="font-medium">{name}</span>
                <span
                    className={"text-destructive"
                        if run.status == "failed"
                        else "text-muted-foreground"}
                >
                    {STATUS_WORDS[run.status]
                        if run.status in STATUS_WORDS
                        else run.status}
                </span>
                <span className="ml-auto flex shrink-0 items-center gap-1">
                    {if run.review_url {
                        <a
                            key="link"
                            href={run.review_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                        >
                            View on GitHub
                        </a>
                    }}
                    {if again {
                        <Button
                            key="retry"
                            size="xs"
                            variant="outline"
                            disabled={busy}
                            onClick={lambda { onRetry(run.id); }}
                        >
                            Retry
                        </Button>
                    }}
                    {if live {
                        <Button
                            key="cancel"
                            size="xs"
                            variant="ghost"
                            disabled={busy}
                            onClick={lambda { onCancel(run.id); }}
                        >
                            Cancel
                        </Button>
                    }}
                </span>
            </div>
            {if line {
                <span key="line" className="text-muted-foreground">{line}</span>
            }}
            {if run.status == "done" and run.summary {
                <p key="sum" className="break-words">{run.summary}</p>
            }}
        </li>;
}
