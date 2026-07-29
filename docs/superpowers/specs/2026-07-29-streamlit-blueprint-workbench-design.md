# Streamlit Blueprint Workbench Design

## Goal

Reshape the existing Streamlit interface into a portfolio-grade AI analytics
workbench without changing the Text-to-SQL workflow, security boundaries, provider
behavior, or runtime configuration.

The primary audience is a technical recruiter or engineering reviewer. The page must
communicate the product purpose, the guarded execution path, and a credible result
within one desktop screenshot while remaining usable on smaller screens.

## Visual direction

The interface uses a **blueprint workbench** metaphor: a precise light canvas surrounds
an ink-colored query console, and cobalt annotations identify trusted transitions.
This keeps the product technical without using a generic dashboard grid.

### Tokens

- Blueprint ink: `#10233F` for the query console and primary text.
- Drafting blue: `#2F6BFF` for primary actions and active states.
- Signal teal: `#16A394` for verified and read-only states.
- Warm paper: `#F7F5F0` for the page canvas.
- Panel white: `#FFFFFF` for result surfaces.
- Rule gray: `#D8DEE9` for borders and structural dividers.
- Display type: `Aptos Display`, falling back to `Segoe UI`.
- Body type: `Aptos`, falling back to `Segoe UI`.
- Utility type: `Cascadia Code`, falling back to a system monospace font.

## Page structure

1. A compact top masthead states the product name, purpose, provider, and database
   readiness. Runtime facts appear as restrained status chips instead of a long
   sidebar inventory.
2. A horizontal trust rail shows the actual ordered workflow: generate, guard,
   execute, and answer. It must fit inside the content width without clipping.
3. A dark query console contains the reviewed-question selector, question input, and
   primary action. The visual contrast makes the user's request the focal point.
4. Successful output starts with a grounded-answer callout, followed by compact
   validation facts, the result table, and a collapsible SQL/technical evidence area.
5. The sidebar remains available for secondary runtime details and session reset, but
   it is visually quieter and narrower than the current implementation.

## Signature element

The memorable element is the **trust rail**: four connected nodes that transition
from model generation to guarded execution and grounded response. The rail encodes a
real sequence and reinforces the project's security thesis rather than serving as
decoration.

## Interaction and states

- The primary button remains disabled when the database is unavailable.
- Running, safe-stop, provider-error, and successful states keep their existing safe
  messages and request references.
- Result data is rendered only from `WorkflowResult`; no new raw provider or exception
  content is exposed.
- SQL remains available to reviewers, but the grounded answer and validation outcome
  appear first for easier scanning.
- Controls retain visible labels, keyboard focus, and sufficient contrast.
- Layout stacks cleanly below tablet width; the trust rail becomes a two-column grid
  and then a single column on narrow screens.
- Reduced-motion preferences are respected. Any entrance treatment is subtle and
  disabled when reduced motion is requested.

## Testing and verification

- Existing safe-presentation unit tests remain green.
- New tests cover any new pure UI presentation helpers before implementation.
- Ruff, format checking, mypy, pytest, offline evaluation, and release verification
  run before publication.
- The live Streamlit page is checked at desktop and narrow widths.
- The repository screenshot uses offline fake mode with a reviewed question and a
  completed result so it remains reproducible and contains no key or paid-provider
  dependency.

## Publication scope

The implementation may update the Streamlit UI, UI-focused tests, the tracked
workbench screenshot, and the README screenshot context. It must not commit `.env`,
local databases, logs, caches, virtual environments, secrets, or Gemini output.

