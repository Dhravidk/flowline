"""The workspace's AI switch and what turning it on sends. Off pauses every
role's AI responsibilities and keeps their settings. The page owns the
settings (ListResponsibilities) and reloads them through `onChanged`.
"""

import from ...services.agents.agents { SetAiEnabled }
import from ...lib.dates { prettyDay }
import from ..ui.switch { Switch }
import from ..ui.skeleton { Skeleton }
import from .SettingRow { SettingRow }
import from "sonner" { toast }

def:pub AiSwitch(
    enabled: bool, enabledAt: str, loading: bool, onChanged: Callable[[], None]
) -> JsxElement {
    has saving: bool = False;

    async def flip(wanted: bool) -> None;

    status = ("On since " + prettyDay(enabledAt[:10]))
        if enabled and enabledAt
        else ("On" if enabled else "Off");
    return
        <div className="surface max-w-[960px]">
            <SettingRow
                label="AI responsibilities"
                hint="Lets a role hand work such as code review to an AI model. Off pauses every responsibility and keeps its settings."
                htmlFor="ai-enabled"
            >
                {if loading {
                    <Skeleton key="sk" className="h-5 w-32"/>
                } else {
                    <div key="switch" className="flex items-center gap-3">
                        <Switch
                            id="ai-enabled"
                            checked={enabled}
                            disabled={saving}
                            onCheckedChange={lambda (v: bool) { flip(v); }}
                        />
                        <span className="text-[13px] text-muted-foreground">
                            {status}
                        </span>
                    </div>
                } }
            </SettingRow>
            <SettingRow
                label="What is sent"
                hint="Only while AI is on, and only for a task a responsibility runs on."
            >
                <div className="flex max-w-[640px] flex-col gap-2 text-[13px]">
                    <ul className="flex list-disc flex-col gap-1 pl-5">
                        <li>
                            The changed files of the task's linked pull request: the diff, never the whole repository.
                        </li>
                        <li>The linked issue's title and description.</li>
                        <li>Your team's instructions for that responsibility.</li>
                    </ul>
                    <p className="text-[12.5px] text-muted-foreground">
                        They go to the AI model provider this Flowline server is set up with. Nothing else in the workspace is sent.
                    </p>
                </div>
            </SettingRow>
        </div>;
}
