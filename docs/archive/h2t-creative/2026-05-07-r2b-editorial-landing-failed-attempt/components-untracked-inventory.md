# Components inventory — r2b worktree at delete time

The r2b-landing worktree's `plugins/h2t-creative/profiles/h2t-editorial/components/` directory contained 21 component candidates at the point of archive. This document classifies them so future work can decide what (if anything) to recover.

Sources are **not** duplicated into this archive. The committed components are reachable on main or on the open editorial pilot branch; the untracked candidates were never preserved as commits and lose their source when the worktree is removed.

## Classification

### A. R1 base — already on `origin/main`

The original h2t-editorial profile shipped with five components on `main`. These are unaffected by the failed attempt and continue to live in the active profile path:

- `nav/`
- `hero/`
- `section/`
- `cta/`
- `footer/`

(The r2b worktree carried locally-modified `section/` files; those modifications are intentionally not preserved — see `README.md` § "What is NOT preserved here".)

### B. Lifted into #119 T6 — on `feat/119-editorial-semantic-landing-pilot`

The semantic editorial pilot branch lifted six System B-Landing primitives extracted during the r2b attempt. They live on the open editorial-pilot branch in commit `887ab50`. They are **not yet on main** — they will land via PR-α (editorial foundation) once the wireframe gate clears them:

- `page-header/`
- `card-grid/`
- `stats/`
- `comparison-table/`
- `flow/`
- `editorial-cta/`

These are the design-system carry-overs: the renderer and skin worked correctly with them. The composition layer is what failed.

### C. Net-new candidates that did NOT make #119

Ten component candidates lived in the r2b worktree as untracked files and were not lifted into the #119 pilot. They were either rejected during the attempt or never reached the lifting step. Their source disappears with the worktree:

- `comp-box/`
- `decomposition-table/`
- `disc/`
- `meta-box/`
- `mmap/`
- `pos-grid/`
- `prohibition-table/`
- `tabs/`
- `tags/`
- `wave-block/`

If a future wireframe explicitly calls for any of these roles, follow `docs/architecture/h2t-creative/EXTENSION_PROTOCOL.md` § Reuse Before Create. Do not resurrect from the worktree as-is — reconstruct against the wireframe.

## How to recover an item from C before worktree deletion

The worktree at `C:/dev/h2t-skills-r2b-landing` retains the source until it is removed. To recover one component:

1. Copy the directory out of the worktree.
2. File a wireframe gate proposal under the new component's intended role.
3. Lift the source into a new branch only after the wireframe is approved.

After the worktree is removed, recovery is no longer possible from this repo. The components in **C** are listed by name only as a record of what was considered.
