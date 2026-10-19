# Step mockup — clickable mockup (product mode)

**Command**: `/mockup [FR-xx… | screens]` · **Tier**: balanced (deep for complex UIs) · **Session**: fresh

**Context**: `python3 tools/context.py mockup`. Only requirements flagged `ui: yes` matter; skip the rest.

## Procedure
1. Derive the screen list and the main user flows from the UI requirements (or from the arguments). Confirm with the user only if the flows are ambiguous.
2. Build **one self-contained HTML file** `reference/mockup/<project-slug>.html`: no build step, inline CSS/JS, realistic sample data in the project language, navigation between screens, the key interactions of each flow, empty/error states for the critical ones. Accessible by default (semantic HTML, labels, keyboard focus, contrast).
3. Name JavaScript render functions after screens (`renderX`) so the map can cite them.
4. Write `reference/product/mockup-reference.md` from the template: table screen/function → FR-xx, behaviors that are normative vs. illustrative, open UX questions.
5. The mockup is a **behavior reference, not an architecture**: no backend calls, no framework choices. For a native, mobile, desktop, embedded or game UI, mimic the target's screen sizes and navigation patterns in the same HTML file; skip the step for products without a UI (`--no-mockup`).
6. If the tool can publish or preview HTML, offer it; otherwise tell the user to open the file in a browser.

**Chat**: screens built, FRs covered / not covered, UX questions (max 8 lines).
**Gate**: the owner sets `status: approved` in `mockup-reference.md`.
