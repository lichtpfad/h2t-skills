# Git Rules

Determine whether a branch is merged by its content, not by `git merge-base --is-ancestor`.
A squash merge creates a commit with no branch parent, so work that landed still looks
unmerged — 10 of 29 branches did. Compare the changed files against main and look for the
squash commit by subject.

Before deleting remote branches, save a manifest of `sha branch`. Once a remote branch is
gone, reflog does not help.
