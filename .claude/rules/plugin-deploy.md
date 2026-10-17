# Plugin Deploy Rules

## Deploying changes to h2t-core / h2t-dev

⛔ NEVER write the local plugin cache as the final deploy — the next `/plugin marketplace
update` wipes all of it. The three `update-plugin.sh` scripts that did exactly that were
deleted in Task 12 of #541; copying files into `~/.claude/plugins/cache/` by hand is the
same mistake.

**Correct sequence:**
1. Commit the changes
2. `git push origin main` — the changes must be on GitHub
3. `/plugin marketplace update lichtpfad`
4. `/reload-plugins`

**Why:** the local cache (`~/.claude/plugins/cache/`) is overwritten on every marketplace
update. Any work not pushed to the repo is lost.

`/plugin marketplace update` may print nothing at all and still have updated the cache.
Confirm the deploy by checking the cache directory and running the deployed code, not by
reading the command's output.
