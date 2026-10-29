"""A reusable read-only process diagram. The same definitions also render as
an ordered step list; neither view executes the depicted business process."""

import from ...models { ProcessView }
import from "react" { useEffect }

def nodeById(steps: list[dict[str, str]], key: str) -> dict[str, str] {
    for s in steps {
        if s["id"] == key {
            return s;
        }
    }
    return {};
}

def routePath(a: dict[str, str], b: dict[str, str], kind: str) -> str {
    ax = float(a["x"]) + 108.0;
    ay = float(a["y"]) + 124.0;
    bx = float(b["x"]) + 108.0;
    targetY = float(b["y"]);
    if kind == "return" {
        ax = float(a["x"]) + 216.0;
        ay = float(a["y"]) + 62.0;
        bx = float(b["x"]) + 216.0;
        targetY = float(b["y"]) + 62.0;
        return f"M {ax} {ay} H 782 V {targetY} H {bx}";
    }
    mid = (ay + targetY) / 2.0;
    return f"M {ax} {ay} C {ax} {mid}, {bx} {mid}, {bx} {targetY}";
}

def:pub ProcessMap(
    process: ProcessView,
    selectedId: str,
    onSelect: Callable[[str], None],
    listView: bool = False
) -> JsxElement {
    has viewport: Ref[any] = Ref(),
        scale: float = 1.0;

    useEffect(
        lambda {
            box = viewport.current;
            chosen = nodeById(process.steps, selectedId);
            if box and chosen and not listView {
                box.scrollTop = max(
                    0.0,
                    float(chosen["y"]) * scale - (float(box.clientHeight) / 2.0)
                        + 62.0 * scale
                );
                box.scrollLeft = max(
                    0.0,
                    (float(chosen["x"]) + 108.0) * scale - float(box.clientWidth) / 2.0
                );
            }
        },
        [selectedId, process.id, listView, scale]
    );

    height = 200.0;
    for s in process.steps {
        height = max(height, float(s["y"]) + 160.0);
    }
    marker = "arrow-" + process.template_key;
    if listView {
        return
            <ol className="process-step-list" aria-label={process.title + " steps"}>
                {for (i, s) in enumerate(process.steps) {
                    <li key={s["id"]}>
                        <button
                            type="button"
                            className={"process-list-node "
                                + ("is-selected" if selectedId == s["id"] else "")}
                            aria-pressed={selectedId == s["id"]}
                            onClick={lambda { onSelect(s["id"]); }}
                        >
                            <span className="process-number">{i + 1}</span>
                            <span className="process-list-copy">
                                <strong>{s["title"]}</strong>
                                <span>{s["owner"]}</span>
                            </span>
                            <span
                                className={"process-status status-"
                                    + s["status"].lower()}
                            >
                                {s["status"]}
                            </span>
                        </button>
                    </li>
                }}
            </ol>;
    }
    return
        <div>
            <div className="process-zoom-controls" aria-label="Diagram scale">
                {for amount in [0.5, 0.75, 1.0] {
                    <button
                        type="button"
                        key={str(amount)}
                        aria-pressed={scale == amount}
                        onClick={lambda { scale = amount; }}
                    >
                        {str(int(amount * 100.0)) + "%"}
                    </button>
                }}
                <span>Scroll to explore · select a step for details</span>
            </div>
            <div
                ref={viewport}
                className="process-map-scroll"
                tabIndex={0}
                aria-label={process.title + " diagram; scroll to explore"}
            >
                <div
                    className="process-map"
                    style={{"height": str(height) + "px", "zoom": str(scale)}}
                >
                    <svg
                        width="800"
                        height={height}
                        className="process-connectors"
                        aria-hidden={True}
                    >
                        <defs>
                            <marker
                                id={marker}
                                markerWidth="7"
                                markerHeight="7"
                                refX="6"
                                refY="3.5"
                                orient="auto"
                            >
                                <path d="M0 0 L7 3.5 L0 7 Z" fill="currentColor"/>
                            </marker>
                        </defs>
                        {for (i, t) in enumerate(process.transitions) {
                            a = nodeById(process.steps, t["source"]);
                            b = nodeById(process.steps, t["target"]);
                            focused = selectedId == t["source"]
                                or selectedId == t["target"];
                            <g key={str(i)}>
                                <path
                                    d={routePath(a, b, t["kind"])}
                                    className={"process-wire "
                                        + (
                                            "is-return "
                                                if t["kind"] == "return"
                                                else ""
                                        )
                                        + ("is-focused" if focused else "")}
                                    markerEnd={"url(#" + marker + ")"}
                                >
                                    <title>{t["label"] or "Next step"}</title>
                                </path>
                                {if t["label"]
                                    and t["kind"] != "return"
                                    and float(b["y"]) > float(a["y"]) {
                                    <text
                                        x={(float(a["x"]) + float(b["x"])) / 2.0
                                            + 116.0}
                                        y={(float(a["y"]) + 124.0 + float(b["y"])) / 2.0
                                            - 6.0}
                                        className="process-wire-label"
                                    >
                                        {t["label"]}
                                    </text>
                                }}
                            </g>
                        }}
                    </svg>
                    {for s in process.steps {
                        <button
                            key={s["id"]}
                            type="button"
                            data-process-step={s["id"]}
                            aria-pressed={selectedId == s["id"]}
                            className={"process-node "
                                + ("is-selected" if selectedId == s["id"] else "")}
                            style={{"left": s["x"] + "px", "top": s["y"] + "px"}}
                            onClick={lambda { onSelect(s["id"]); }}
                        >
                            <span
                                className={"process-status status-"
                                    + s["status"].lower()}
                            >
                                {s["status"]}
                            </span>
                            <strong>{s["title"]}</strong>
                            <span className="process-node-owner">{s["owner"]}</span>
                        </button>
                    }}
                </div>
            </div>
        </div>;
}
