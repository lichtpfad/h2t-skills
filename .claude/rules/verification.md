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
