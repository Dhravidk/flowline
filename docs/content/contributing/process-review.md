# Review the four delivery processes locally

The process library at `/processes` is a working review milestone. It stores
current and proposed React migration and BAU definitions, without changing the
workspace's operational flow line, board or tasks.

## Start and open

Use the pinned Jac 0.38.2 toolchain from the repository root:

```sh
jac install
jac run --no-dev --host 127.0.0.1 -w 1 main.jac
```

Open `http://localhost:8000/processes`. Sign up or sign in to a **local**
workspace using email and password. Hosted Flowline accounts are stored on a
different server. Google/GitHub SSO needs project credentials and is not
configured for this local review.

Choose **Add the four example flows** once. This saves the definitions to the
workspace. Repeating the installation preserves their IDs and review notes.
The installer adds nothing to the operational board.

Direct links after installation:

| Flow | Local URL |
| --- | --- |
| React migration — current | `http://localhost:8000/processes?family=react&version=current` |
| React migration — proposed | `http://localhost:8000/processes?family=react&version=proposed` |
| BAU — current | `http://localhost:8000/processes?family=bau&version=current` |
| BAU — proposed | `http://localhost:8000/processes?family=bau&version=proposed` |

## Review the process

Select the family and version, or compare both versions. Click a diagram step,
use **Jump to step**, or switch to the readable step list. The inspector shows
the owner, action, decision rule, inputs, outputs, dependencies and rework
destinations. Solid lines move forward; dashed lines return for revision or
repair. Select a step to highlight its connections. The diagram can be scrolled
and viewed at 50%, 75% or 100%.

Save feedback in **Review note**. Notes persist in the local workspace and
survive navigation and reload. A note is not an approval or execution result.

**Shared QA & rules** records the agreed testing, review, repair, timing and
evidence requirements. **To configure** lists values that are deliberately
unset. **Build stages** separates this working milestone from later operational
contributions. The full implementation plan is in
`docs/plans/delivery-workflows.md`.

## Capability labels

| Label | Meaning in this review build |
| --- | --- |
| Working locally | Definition persistence, flow selection/comparison, diagram/list views, step inspection and saved notes |
| Manual | A person performs the depicted business action; the library describes it |
| Planned | Automation or enforcement has not been implemented |
| Placeholder | An unavailable adapter or proprietary tool, including Reactinator, developer agent sets, Spark and Ally integrations |
| To configure | Actual screens/states, references, thresholds, environment, test data and execution limits remain unset |

There is no process executor in this milestone. It does not run agents or QA,
enforce approvals, start clocks, collect delivery evidence, open PRs, merge or
deploy. No missing configuration or unexecuted check is represented as passed.

The current flows include QA staff approval of stories and acceptance criteria
in Spark before development. Proposed flows approve the spec/criteria before
autonomous story validation and implementation, with no routine intermediate
human QA checkpoint. The PR owner performs final human review and may merge
their own PR. Automated BAU regression precedes merge, and business-user UAT
follows merge. UAT rejection creates new linked work that repeats the relevant
story validation and verification steps.

## Verification

Against the running server:

```sh
python tests/smoke/process_gate.py http://localhost:8000
python tests/smoke/process_browser_gate.py http://localhost:8000
```

The API gate uses Python's standard library. The browser gate requires
`playwright` and an installed Chrome; it creates an isolated test workspace
and saves screenshots under `.jac/process-review/`. The tested 1440px and
390px widths exercise this library's own UI, and do not set a project's QA
screen matrix. Tests do not exercise any of the planned delivery automation.
