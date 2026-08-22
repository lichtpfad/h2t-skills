# Plugin Deploy Rules

## Deploying changes to h2t-core / h2t-dev

⛔ NEVER use `update-plugin.sh` as the final deploy — it writes to the local cache only, and
the next `/plugin marketplace update` wipes all of it.

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
