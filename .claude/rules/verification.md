# Verification Rules

Judge the state, not the report of the state. `/plugin marketplace update` printed nothing
where it had printed a success line before — and had updated the cache anyway. Check the
thing itself.

A zero measurement means nothing until the same probe returns non-zero in a case known to
be positive. Without that control, "not found" and "broken instrument" are indistinguishable.

A red test is not a passed check until its failure text is read. A test can die before the
assertion that matters — an emptied PATH gave `cat: command not found`, which looked exactly
like the bug being caught.

When two components share a contract (writer/reader, hook/handler, producer/consumer), test
the round trip. Each side's own tests stay green while the sides disagree; the defect lives
in the seam.

`$?` after a pipe is the last command's status, not the one you care about. `lint.py doctor
2>&1 | tail -6; echo $?` printed 0 while doctor was exiting 1 — and that reading went into a
rules file as "verified: exits 0". Redirect to /dev/null and read `$?`, or use
`${PIPESTATUS[0]}`. The same shape truncates evidence: a `grep ... | head` that fills its
quota from one file reads exactly like a grep that found nothing anywhere else.

## A new test counts only after it has been seen red

A green test proves nothing on its own: it may be asserting on a representation where
the defect is not visible. Before trusting a test you just wrote, run it against the
broken state — revert the fix, or run it on the commit before. If it does not go red,
it is a comment, not a test.

Three instances in one session, 2026-08-27, all the same error in different clothes:

- `monkeypatch.setattr(Path, "home", ...)` while the code called `Path.expanduser()`,
  which resolves `~` through `os.environ["HOME"]`. The patch was inert.
- Four tests patched `_DEV_ROOT`, declared and never read; the function used
  `_H2T_DEV_ROOT`, resolved at import. The patch was inert (#434).
- A surrogate check ran on the parsed envelope. `json.dumps` writes the six ASCII
  characters `\udcd1` and Python's `json.loads` accepts them, so both the regex and the
  parser reported clean while the API rejected the request (#453).

The shared shape: **the assertion sat downstream of a step that normalizes the defect
away, and the patch named a source the code does not read.** Do not infer which source
a function reads — open the line and read it. `Path.home()` and `os.environ["HOME"]` are
not the same source; a module constant and a call at runtime are not the same source; the
parsed value and the bytes are not the same representation.

Cheapest defense, and the only one that has actually worked here: revert the fix, watch
the test go red, restore. Two commands.

## Name the area yourself; do not inherit it from the tool

A tool answers the question its defaults ask, not the one you meant. Before running a
check, say out loud what it must cover — then confirm the invocation covers that.

Measured 2026-08-27, after rewriting history to remove two tokens:

```
gitleaks detect                      -> no leaks found
gitleaks detect --log-opts="--all"   -> leaks found: 2
```

Both true. `detect` walks what a clone reaches, and `refs/pull/*` are not fetched by
default, so 147 of 148 pull-request refs still carried the secret while the first command
reported the repository clean. The result was announced as "history is clean" on the
strength of the narrower run.

The same shape appears wherever a default bounds the scan: a `grep --include=*.py` that
answers about Python and gets read as answering about the tree; a probe writing to a file
when the defect lives on the console path; a suite run on one directory when CI runs
fourteen. In each case the tool is honest and the conclusion is wrong.

Two habits close it. State the area before the command, not after the output. And when a
check returns clean on something that was dirty a moment ago, widen it once before
believing it.

## An audit is a measurement; only a test is a gate

An audit answers "how many are there now". A test answers "did it get worse". The first
expires as it is printed, and it takes a reader to act on it; the second survives the
session, the compaction and the change of hands.

Measured 2026-08-27 on #434. The pre-release audit was not blind — its phase C counted
**183** occurrences in the shipping directories and called them "the whole problem". A
commit titled `fix: derive where sibling repos live instead of naming C:/dev (#434)`
followed, removing **10 of 45** live `C:/dev` occurrences. The number in the subject
reads as closure, and it was read that way here months later. No test existed:
`git log` over `tests/**/*author*` and `*hardcode*` was empty until the ratchet was
written, and by then twelve occurrences remained, three of them behaviour rather than
prose.

So: judge "is it done" by state, never by an issue number in a commit subject. And when
an audit produces a list, the deliverable is not the list — it is whatever will fail
tomorrow if the list grows.

## After writing a guard, ask separately what it does not cover

A guard encodes the shape of the defect at the moment it was found, and then protects
that shape. The regex reads like "the rule about author paths" and is "the rule about
`C:/dev`".

Three instances in one session, 2026-08-27, none of them found by the guard itself:

- The author-path ratchet matched `C:/dev` and missed
  `C:/Program Files/GitHub CLI/gh.exe` — same class, different literal.
- It walked `plugins/` while `h2t_ops/` is the package behind the nine CLI entry points,
  the first thing a stranger installs. The hint telling them to install from
  `C:/dev/h2t-tools` sat there untouched.
- The interpreter guard forbade a *path* to an interpreter and said nothing about calling
  one by name, so reverting a file to `python3` left the suite green.

Each was found by a grep over the whole tree, in the minutes after the guard went in.

The remedy is not "write it wider" — wider catches `/Users/x/` in a fixture. It is one
deliberate question after the guard passes: **which files does this not read, and which
spellings does it not match?** Three minutes of grep answered it every time.
