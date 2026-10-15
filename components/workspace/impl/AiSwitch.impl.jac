"""Implementations for the AI switch."""

impl AiSwitch.flip(wanted: bool) -> None {
    if saving {
        return;
    }
    saving = True;
    try {
        result = root spawn SetAiEnabled(enabled=wanted);
        answer: any = result.reports[0] if result.reports else None;
        if answer and answer["ok"] {
            await onChanged();
            toast.success(
                "AI responsibilities turned on"
                    if wanted
                    else "AI responsibilities paused"
            );
        } else {
            toast.error("Could not change the AI setting");
        }
    } except Exception as e {
        toast.error("Could not change the AI setting");
    }
    saving = False;
}
