# Git Rules

Determine whether a branch is merged by its content, not by `git merge-base --is-ancestor`.
A squash merge creates a commit with no branch parent, so work that landed still looks
unmerged — 10 of 29 branches did. Compare the changed files against main and look for the
squash commit by subject.

Before deleting remote branches, save a manifest of `sha branch`. Once a remote branch is
gone, reflog does not help.

For a **local** branch, deletion is recoverable — the opposite case, and worth knowing before
you panic. `git branch -D` removes the ref, not the objects: `git fsck --lost-found` lists the
dangling commit, and `git checkout <sha> -- <paths>` takes back exactly the paths you name.
Measured 2026-08-28: 6f5d09de held 80 files that had left the working tree minutes earlier.

They left it because of `git add -A` inside a scratch branch. Stash, branch, `stash pop`,
`add -A`, commit — and a full session of uncommitted work rode into the probe commit, then
out of the tree with the branch. Stage explicit paths when the branch exists to test
something (`git add <path>`), or do not mix a gate probe with unsaved work at all: commit
your own first, then set up the probe.
