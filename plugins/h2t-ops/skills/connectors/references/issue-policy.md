# Connector Issue Policy

Use this policy when an h2t-ops connector command is missing, returns the wrong shape, fails with a provider bug, or forces an agent toward raw provider API code.

## Bug vs Feature

- Bug: a documented `h2t-ops CONNECTOR VERB` command exists but fails, returns the wrong output shape, leaks raw errors, or violates the connector boundary.
- Feature: a useful provider operation is not exposed by `h2t-ops`.

## Filing

Privacy rules, the body headings, the user's consent and the `gh` command live in one
place: the `h2t-core:report-issue` skill. Load it and follow it from its Step 3. Add to
its `Steps to reproduce` the connector, the command, and whether it was a read or a write.
