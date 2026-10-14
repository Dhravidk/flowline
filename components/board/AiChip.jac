"""The row's AI chip while a run is open on the task: queued, or reviewing
with a pulsing dot. Nothing renders once the run settles."""

def:pub AiChip(state: str) -> JsxElement {
    running = state == "running";
    return
        <span
            className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-muted px-2 py-px text-xs text-muted-foreground"
            title={"An AI review is running on the linked pull request"
                if running
                else "An AI review is queued for the linked pull request"}
        >
            <span
                aria-hidden="true"
                className={"size-1.5 rounded-full "
                    + (
                        "animate-pulse bg-status-review"
                            if running
                            else "bg-status-todo"
                    )}
            />
            {"AI reviewing" if running else "AI review queued"}
        </span>;
}
