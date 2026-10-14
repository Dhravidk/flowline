"""Where an AI responsibility runs (the role's own steps) and how far it may
go (comment only, or send the task back), as toggle chips like the member
dialog's. No step picked means every step the role owns.
"""

import from ....models { StepView }
import from ...ui.label { Label }
import from ..icons { IconCheck }

glob MODES: list[list[str]] = [
         ["comment", "Comment only"],
         ["request_changes", "Request changes"]
     ];

def Pick(label: str, on: bool, onClick: Callable[[], None]) -> JsxElement {
    return
        <button
            type="button"
            aria-pressed={on}
            className={"inline-flex h-7 items-center gap-1.5 rounded-sm border px-2 text-[13px] transition-colors duration-150 "
                + (
                    "border-foreground bg-card font-semibold text-foreground"
                        if on
                        else "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
            onClick={lambda { onClick(); }}
        >
            {if on {
                <IconCheck key="tick" size={12}/>
            }}
            <span>{label}</span>
        </button>;
}

def:pub ResponsibilityScope(
    mode: str,
    picked: list[str],
    steps: list[StepView],
    onField: Callable[[str, str], None],
    onToggleStep: Callable[[str], None]
) -> JsxElement {
    hint = "Runs only where you pick; none picked means every step this role owns."
        if len(steps) > 0
        else "This role owns no step yet. Make it a step's owner on the flow line.";
    reach = "A blocking problem sends the task back along the flow line."
        if mode == "request_changes"
        else "Leaves a review with comments. The task stays where it is.";
    return
        <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
                <Label>Runs on</Label>
                <div className="flex flex-wrap gap-1.5">
                    {for s in steps {
                        <Pick
                            key={s.id}
                            label={s.name}
                            on={s.id in picked}
                            onClick={lambda { onToggleStep(s.id); }}
                        />
                    }}
                </div>
                <p className="text-[12.5px] text-muted-foreground">{hint}</p>
            </div>
            <div className="flex flex-col gap-2">
                <Label>How far it may go</Label>
                <div className="flex flex-wrap gap-1.5">
                    {for m in MODES {
                        <Pick
                            key={m[0]}
                            label={m[1]}
                            on={mode == m[0]}
                            onClick={lambda { onField("mode", m[0]); }}
                        />
                    }}
                </div>
                <p className="text-[12.5px] text-muted-foreground">{reach}</p>
            </div>
        </div>;
}
