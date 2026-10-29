"""Inspect intended behavior and save review notes. Notes are not approvals,
execution evidence, or workflow state changes."""

import from ...models { ProcessView }
import from ...services.processes.processes { SaveProcessNote }
import from .ProcessMap { nodeById }

def:pub StepReview(
    process: ProcessView,
    step: dict[str, str],
    onSaved: Callable[[], any],
    onJump: Callable[[str], None]
) -> JsxElement {
    has note: str = process.review_notes[step["id"]]
        if step["id"] in process.review_notes
        else "",
        message: str = "",
        busy: bool = False;

    async def save {
        busy = True;
        message = "";
        try {
            result = root spawn SaveProcessNote(
                process_id=process.id, step_id=step["id"], note=note
            );
            data = result.reports[0] if result.reports else {};
            message = "Saved to this workspace"
                if data.get("ok", False)
                else "Could not save this note. Try again.";
            if data.get("ok", False) {
                await onSaved();
            }
        } except Exception {
            message = "Could not save this note. Try again.";
        }
        busy = False;
    }

    return
        <aside className="process-inspector" aria-label="Step details">
            <div className="process-eyebrow">STEP DETAILS</div>
            <h2>{step["title"]}</h2>
            <div className="process-detail-badges">
                <span className={"process-status status-" + step["status"].lower()}>
                    {step["status"]}
                </span>
                <span className="process-muted">
                    {step["mode"] + " · " + step["owner"]}
                </span>
            </div>
            <p>{step["detail"]}</p>
            <dl className="process-detail-list">
                <dt>Entry / decision rule</dt>
                <dd>{step["guard"]}</dd>
                <dt>Inputs</dt>
                <dd>{step["inputs"]}</dd>
                <dt>Outputs</dt>
                <dd>{step["outputs"]}</dd>
                <dt>Tools / dependencies</dt>
                <dd>{step["tool"]}</dd>
            </dl>
            <h3>Next steps and rework</h3>
            <ul className="process-transitions">
                {for (i, t) in enumerate(process.transitions) {
                    if t["source"] == step["id"] {
                        <li key={str(i)}>
                            <span
                                className={"process-transition-dot "
                                    + ("is-return" if t["kind"] == "return" else "")}
                            />
                            <span>
                                {t["label"] or "Continue"}
                                <button
                                    type="button"
                                    className="process-jump-link"
                                    onClick={lambda { onJump(t["target"]); }}
                                >
                                    {nodeById(process.steps, t["target"])["title"]
                                        + " →"}
                                </button>
                            </span>
                        </li>
                    }
                }}
            </ul>
            <div className="process-note">
                <label htmlFor="process-note">Review note</label>
                <p className="process-muted">
                    A saved comment on this step. This does not approve or execute it.
                </p>
                <textarea
                    id="process-note"
                    value={note}
                    rows={4}
                    maxLength={6000}
                    placeholder="What should we change or clarify?"
                    onChange={lambda (e: ChangeEvent) {
                        note = e.target.value;
                        message = "Unsaved changes";
                    }}
                />
                <button
                    type="button"
                    className="process-button primary"
                    disabled={busy}
                    onClick={save}
                >
                    {"Saving…" if busy else "Save note"}
                </button>
                <p role="status" className="process-muted">{message}</p>
            </div>
        </aside>;
}
