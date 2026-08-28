# h2t-creative Changelog

## Unreleased

- feat(browser-qa): the QA agent ships with the plugin. `landing` and `deck` required
  `h2t-tools:playwright-agent` and halted delivery without it — a plugin in nobody's install,
  which made both skills unexecutable as written rather than merely unverified. What was
  actually needed was 40 lines of agent frontmatter: an MCP command (`npx @playwright/mcp`)
  and a tool allowlist. Absorbed as `h2t-creative:browser-qa`, scoped to the job — three
  widths, `scrollWidth` against `clientWidth`, console, keyboard smoke test for a deck — and
  told not to edit anything or judge the design

- fix(landing, deck): a missing QA tool no longer stops delivery. `dist/` ships with the
  message saying it is unverified and at which widths, because a page nobody looked at beats
  a page nobody built; what is not acceptable is delivering one and implying the other (#460)
