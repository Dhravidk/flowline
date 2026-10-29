"""Process library: four persisted example storyboards, current/proposed
comparison, explicit capability labels and saved step review notes."""

import from ...models { ProcessView }
import from ...services.processes.processes { ListProcesses, InstallProcessExamples }
import from ...components.processes.ProcessMap { ProcessMap, nodeById }
import from ...components.processes.StepReview { StepReview }
import from ...lib.workspace { loadWorkspace }

def:pub ProcessesPage -> JsxPage {
    has processes: list[ProcessView] = [],
        family: str = "react",
        variant: str = "current",
        compare: bool = False,
        listView: bool = False,
        tab: str = "flow",
        selectedId: str = "intake",
        loading: bool = True,
        busy: bool = False,
        error: str = "";

    async can with entry {
        w: any = window;
        params: any = new(w.URLSearchParams, w.location.search);
        if params.get("family") in ["react", "bau"] {
            family = str(params.get("family"));
        }
        if params.get("version") in ["current", "proposed"] {
            variant = str(params.get("version"));
        }
        compare = params.get("compare") == "1";
        load();
        loadWorkspace();
    }

    async def load {
        loading = True;
        error = "";
        try {
            result = root spawn ListProcesses();
            processes = result.reports[0] if result.reports else [];
        } except Exception {
            error = "Could not load the process library. Your saved work has not changed.";
        }
        loading = False;
    }

    async def install {
        busy = True;
        error = "";
        try {
            result = root spawn InstallProcessExamples();
            data = result.reports[0] if result.reports else {};
            if data.get("ok", False) {
                await load();
            } else {
                error = "Could not install the examples. Please try again.";
            }
        } except Exception {
            error = "Could not install the examples. Please try again.";
        }
        busy = False;
    }

    async def refreshNotes {
        result = root spawn ListProcesses();
        processes = result.reports[0] if result.reports else processes;
    }

    def pickFamily(value: str) {
        family = value;
        selectedId = "intake";
        rememberSelection();
    }
    def pickVariant(value: str) {
        variant = value;
        selectedId = "intake";
        rememberSelection();
    }
    def selectStep(value: str, version: str) {
        selectedId = value;
        variant = version;
        rememberSelection();
    }
    def rememberSelection {
        window.history.replaceState(
            None,
            "",
            "/processes?family="
                + family
                + "&version="
                + variant
                + ("&compare=1" if compare else "")
        );
    }

    visible = [
        p
        for p in processes
        if p.family == family and (compare or p.variant == variant)
    ];
    picked = [
        p
        for p in processes
        if p.family == family and p.variant == variant
    ];
    active = picked[0] if picked else None;
    selected = nodeById(active.steps, selectedId) if active else {};

    return
        <div className="process-library">
            <header className="process-page-header">
                <div>
                    <div className="process-eyebrow">PROCESS LIBRARY</div>
                    <h1>From request to release</h1>
                    <p className="process-muted">
                        Review the React migration and BAU processes, and the automation we could build next.
                    </p>
                </div>
                <span className="process-status status-working">
                    Local review · working
                </span>
            </header>
            <div className="process-notice">
                <strong>Storyboards only</strong>
                <span>
                    Flow selection, comparison, step details and saved review notes work. Automation, enforced approvals, QA execution, timers and integrations are unfinished. No delivery checks have run.
                </span>
            </div>
            {if error {
                <div key="error" role="alert" className="process-error">
                    {error}
                    <button type="button" className="process-button" onClick={load}>
                        Retry
                    </button>
                </div>
            }}
            {if loading {
                <p key="loading" role="status">Loading your process library…</p>
            } elif not processes and not error {
                <section key="empty" className="process-empty">
                    <h2>Four processes, one place to review</h2>
                    <p>
                        Install current and proposed versions of the React migration and BAU flows. They are saved to your workspace alongside your operational flow.
                    </p>
                    <button
                        type="button"
                        className="process-button primary"
                        disabled={busy}
                        onClick={install}
                    >
                        {"Installing…" if busy else "Add the four example flows"}
                    </button>
                </section>
            } elif processes {
                <div key="library">
                    <div className="process-controls">
                        <div className="process-segment" aria-label="Process family">
                            <button
                                type="button"
                                aria-pressed={family == "react"}
                                onClick={lambda { pickFamily("react"); }}
                            >
                                React migration
                            </button>
                            <button
                                type="button"
                                aria-pressed={family == "bau"}
                                onClick={lambda { pickFamily("bau"); }}
                            >
                                BAU
                            </button>
                        </div>
                        <div className="process-segment" aria-label="Process version">
                            <button
                                type="button"
                                aria-pressed={variant == "current"}
                                onClick={lambda { pickVariant("current"); }}
                            >
                                Current
                            </button>
                            <button
                                type="button"
                                aria-pressed={variant == "proposed"}
                                onClick={lambda { pickVariant("proposed"); }}
                            >
                                Proposed
                            </button>
                        </div>
                        <button
                            type="button"
                            className="process-button"
                            aria-pressed={compare}
                            onClick={lambda {
                                compare = not compare;
                                rememberSelection();
                            }}
                        >
                            {"Single view" if compare else "Compare versions"}
                        </button>
                    </div>
                    {if active {
                        <div key="summary" className="process-summary">
                            <h2>{active.title}</h2>
                            <p>{active.summary}</p>
                            <span className="process-muted">
                                {"Definition v"
                                    + str(active.revision)
                                    + " · saved to this workspace · no execution evidence"}
                            </span>
                        </div>
                    }}
                    <div className="process-tabs" aria-label="Review sections">
                        {for pair in [
                            ["flow", "Flowchart"],
                            ["rules", "Shared QA & rules"],
                            ["setup", "To configure"],
                            ["delivery", "Build stages"]
                        ] {
                            <button
                                key={pair[0]}
                                type="button"
                                aria-pressed={tab == pair[0]}
                                onClick={lambda { tab = pair[0]; }}
                            >
                                {pair[1]}
                            </button>
                        }}
                    </div>
                    {if tab == "flow" {
                        <section key="flow" className="process-flow-section">
                            <div className="process-map-toolbar">
                                <div className="process-legend">
                                    <span className="process-status status-manual">
                                        Manual
                                    </span>
                                    <span className="process-status status-planned">
                                        Planned
                                    </span>
                                    <span className="process-status status-placeholder">
                                        Placeholder
                                    </span>
                                    <span className="process-muted">
                                        Solid: forward · Dashed: return / rework
                                    </span>
                                </div>
                                {if active {
                                    <label key="jump" className="process-jump-select">
                                        <span>Jump to step</span>
                                        <select
                                            aria-label="Jump to step"
                                            value={selectedId}
                                            onChange={lambda (e: ChangeEvent) { selectedId = e.target.value; }}
                                        >
                                            {for s in active.steps {
                                                <option key={s["id"]} value={s["id"]}>
                                                    {s["title"]}
                                                </option>
                                            }}
                                        </select>
                                    </label>
                                }}
                                <button
                                    type="button"
                                    className="process-button"
                                    aria-pressed={listView}
                                    onClick={lambda { listView = not listView; }}
                                >
                                    {"Show diagram" if listView else "Show step list"}
                                </button>
                            </div>
                            <div
                                className={"process-review-layout "
                                    + ("is-comparing" if compare else "")}
                            >
                                <div
                                    className={"process-diagrams "
                                        + ("is-comparing" if compare else "")}
                                >
                                    {for p in visible {
                                        <section
                                            key={p.id}
                                            className="process-diagram-panel"
                                        >
                                            <div className="process-panel-title">
                                                <h3>{p.variant.capitalize()}</h3>
                                                <span className="process-muted">
                                                    {str(len(p.steps))
                                                        + " steps · click to inspect"}
                                                </span>
                                            </div>
                                            <ProcessMap
                                                process={p}
                                                selectedId={selectedId
                                                    if p.variant == variant
                                                    else ""}
                                                listView={listView}
                                                onSelect={lambda (value: str) { selectStep(
                                                    value, p.variant
                                                ); }}
                                            />
                                        </section>
                                    }}
                                </div>
                                {if active and selected {
                                    <StepReview
                                        key={active.id + selectedId}
                                        process={active}
                                        step={selected}
                                        onSaved={refreshNotes}
                                        onJump={lambda (value: str) { selectedId = value; }}
                                    />
                                }}
                            </div>
                        </section>
                    } elif tab == "rules" and active {
                        <div key="rules" className="process-policy-grid">
                            {for rule in active.policies {
                                <article key={rule["title"]} className="process-policy">
                                    <span className="process-status status-planned">
                                        Planned enforcement
                                    </span>
                                    <h3>{rule["title"]}</h3>
                                    <p>{rule["detail"]}</p>
                                </article>
                            }}
                        </div>
                    } elif tab == "setup" and active {
                        <div key="setup">
                            <p className="process-config-intro">
                                These values are deliberately unset. This review build shows the required setup; it does not provision environments or save a quality profile.
                            </p>
                            <div className="process-policy-grid">
                                {for item in active.configuration {
                                    <article
                                        key={item["title"]}
                                        className="process-policy"
                                    >
                                        <span
                                            className="process-status status-placeholder"
                                        >
                                            {item["status"]}
                                        </span>
                                        <h3>{item["title"]}</h3>
                                        <p>{item["detail"]}</p>
                                    </article>
                                }}
                            </div>
                        </div>
                    } elif tab == "delivery" {
                        <div key="delivery" className="process-policy-grid">
                            <article className="process-policy">
                                <span className="process-status status-working">
                                    Working locally
                                </span>
                                <h3>1 · Process review library</h3>
                                <p>
                                    Persist four definitions per workspace, switch and compare versions, inspect steps and save review notes. The operational board stays separate.
                                </p>
                            </article>
                            <article className="process-policy">
                                <span className="process-status status-planned">
                                    Planned
                                </span>
                                <h3>2 · Versioned delivery records</h3>
                                <p>
                                    Spec / story / AC / task / scenario traceability, approvals tied to identities and versions, then project configuration and validation.
                                </p>
                            </article>
                            <article className="process-policy">
                                <span className="process-status status-planned">
                                    Planned
                                </span>
                                <h3>3 · QA and evidence</h3>
                                <p>
                                    Execute required checks, collect commit/build-specific evidence, detect layout defects, retain retries and enforce the non-resetting QA deadline.
                                </p>
                            </article>
                            <article className="process-policy">
                                <span className="process-status status-planned">
                                    Planned
                                </span>
                                <h3>4 · Review, repair and readiness</h3>
                                <p>
                                    Independent read-only review, bounded repair and exchanges, pause/resume decisions, current evidence bundle and final PR-owner checkpoint.
                                </p>
                            </article>
                            <article className="process-policy">
                                <span className="process-status status-placeholder">
                                    Placeholder
                                </span>
                                <h3>5 · Adapters and pilot</h3>
                                <p>
                                    Connect generic git, preview and test runners. Reactinator, developer agent sets, Spark and Ally integrations remain labelled placeholders.
                                </p>
                            </article>
                        </div>
                    }   }
                </div>
            }  }
        </div>;
}
