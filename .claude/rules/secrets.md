# Secrets Rules

## Excision is incomplete where pull requests exist; rotation is the control

A secret committed to a repository that has ever had a pull request cannot be fully removed
by rewriting history. GitHub keeps `refs/pull/*/head` server-side, and a force-push does not
touch them — the client has no way to rewrite them at all.

Measured 2026-08-27 on `lichtpfad/h2t-skills`, after `git filter-repo --replace-text` and a
force-push of every branch and tag:

```
fresh clone, branches and tags   gitleaks: no leaks found
same clone + refs/pull/*         gitleaks: leaks found: 2
147 of 148 pull-request refs still carried the tainted commit
```

So the order of operations is fixed:

1. **Rotate first.** A rotated secret makes every surviving copy worthless, whatever refs,
   caches, forks, clones or transcripts hold it. This is the only step that always works.
2. Rewrite history second, and only for tidiness — so a reader of the branches does not
   trip over a dead credential and waste a day deciding whether it is live.
3. Never treat a clean `gitleaks` run as proof. Run it with `--log-opts="--all"` after
   fetching `refs/pull/*`, and expect the pull-request refs to stay dirty forever.

Rewriting still earns its place: it is cheap, it is reversible from a mirror, and it stops
the value from reaching anyone reading the tree. It just is not the control.

## Before rewriting history

`.claude/rules/git.md` requires a `sha branch` manifest before deleting remote branches; a
rewrite needs more, because every SHA moves at once.

1. Write the manifest of every ref: branches, remotes, tags, HEAD.
2. `git clone --mirror` the repository to a dated directory outside it.
3. Rewrite, then verify against the mirror by count, not by eye: commits, files, tags.
4. Re-run the secret scan over the widened area.
5. `git filter-repo` removes the `origin` remote by design. Restore it before pushing —
   and expect anything that resolves repository identity through `git remote` to fail
   until you do.
6. Warn every other checkout **before** the force-push lands, and say plainly that a plain
   `git pull` will produce a garbage merge.

## Never print a secret to verify its removal

Confirm by absence, not by display: grep for the literal and report the match count, or
mask all but a few characters. A `diff` that shows the redaction shows the original — on
2026-08-27 that put both tokens into a session transcript they had never been in before,
and turned a rotation that could wait into one that could not.

## Verify a revocation with the value from the leak, never from your own store

Two questions look identical and are not. *Does my access still work?* is answered by the
value in `~/.dor/secrets.env`. *Does the attacker's copy still work?* is answered only by the
literal sitting in the public artifact. Publication turns on the second.

Measured 2026-08-28, and it cost three hours on the day of a talk. A rotation had landed; the
peer reported the leaked pair dead with a control (`old → 401 ×8`, `new → 200`, `fake → 401`).
This side probed with the value read from `~/.dor/secrets.env`, got 200, and declared the
leak live. The file had been synced from the machine that performed the rotation minutes
earlier — the probe was sending the **new** token and getting a legitimate 200.

The discriminator was one hash:

```
sha256[:12] of what was actually being sent   59e311ce09e1   ← the new ro
sha256[:12] of the literal in the leak        a0d4dbd035ab
```

Re-probed with the literal taken from history, not from the file:

```
git show <sha>:<path> | sed -n '<line>p'     → 401 E_AUTH_INVALID
value from the local file                    → 200            (positive control)
sixty-four zeroes                            → 401            (negative control)
```

So: take the value from `git show <sha>:<file>`, which cannot change under you. A local
secrets file is a moving target — Syncthing, a peer's rotation, a manual edit — and it moved
between two commands in one session here.

## The redaction a tool promises is not redaction you have

`gstack browse` documents that `header` auto-redacts sensitive values. It printed the token
verbatim in its `Header set:` line on 2026-08-28. Earlier the same session, `gitleaks --redact`
blanked its own `Secret` field, which broke a masking routine built on substring replacement —
the substring no longer matched the file line, and the raw line was printed instead.

Both failures share a shape: **the defence assumed a property of someone else's output.** The
working form assumes nothing. Never print a line that contains the match, in any form. Emit
metadata only — rule, file, commit, line number, length — and compare by hash. That is what
the rotation check above did, and nothing leaked through it.
