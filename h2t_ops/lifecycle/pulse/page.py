"""The browser page of the pulse: one static HTML file over the same rows as the terminal view.

Rows go in as a JSON block; a small script filters them and groups them as `view.render` does.
Nothing is fetched: no fonts, no scripts, no URLs.
"""

from __future__ import annotations

import json
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.lifecycle.pulse import view

_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Сессии</title>
<style>
:root { color-scheme: light dark; --bg: #fff; --fg: #1d1d1f; --mute: #6b6b70; --line: #d8d8dc; --acc: #0a5bd3; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #17171a; --fg: #e8e8ea; --mute: #9a9aa2; --line: #34343a; --acc: #6aa3ff; }
}
body { margin: 0; padding: 12px 16px 32px; background: var(--bg); color: var(--fg);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 18px; margin: 0 0 8px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.filters label { display: flex; flex-direction: column; font-size: 12px; color: var(--mute); }
.filters select, .filters input { font: inherit; color: var(--fg); background: var(--bg);
  border: 1px solid var(--line); border-radius: 4px; padding: 3px 6px; min-width: 7em; }
.filters .check { flex-direction: row; align-items: end; gap: 4px; }
.filters .check input { min-width: 0; }
.g1 { font-weight: 600; font-size: 16px; margin-top: 16px; }
.g2 { font-weight: 600; margin: 8px 0 0 12px; }
.g3 { margin: 4px 0 0 24px; color: var(--mute); word-break: break-all; }
.g4 { margin: 6px 0 0 36px; }
.branch { font-family: ui-monospace, Consolas, monospace; font-size: 13px; }
.sess { margin: 4px 0 0 48px; padding-left: 8px; border-left: 2px solid var(--line); }
.meta { color: var(--mute); font-size: 12px; }
.summary { white-space: pre-wrap; }
.cmd { display: flex; gap: 8px; align-items: center; margin-top: 2px; }
.cmd code { font: 12px ui-monospace, Consolas, monospace; word-break: break-all; flex: 1; }
button { font: inherit; font-size: 12px; color: var(--acc); background: none;
  border: 1px solid var(--line); border-radius: 4px; padding: 2px 8px; cursor: pointer; }
.foot { margin-top: 24px; color: var(--mute); border-top: 1px solid var(--line); padding-top: 8px; }
@media (max-width: 600px) { .g2, .g3, .g4, .sess { margin-left: 8px; } }
</style>
</head>
<body>
<h1>Сессии</h1>
<div class="filters" id="filters"></div>
<div id="tree"></div>
<div class="foot" id="count"></div>
<div class="foot" id="footer"></div>
<script type="application/json" id="data">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById("data").textContent);
  var DASH = "\\u2014";
  var SELECTS = [["domain", "домен"], ["project", "проект"], ["verdict", "статус"],
                 ["pr", "PR"], ["tool", "tool"]];
  var state = {repo: "", since: "", unknown: false};

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function field(label, input) {
    var l = el("label", "", label);
    l.appendChild(input);
    return l;
  }
  function uniq(key) {
    var seen = {};
    D.rows.forEach(function (r) { if (r[key]) seen[r[key]] = 1; });
    return Object.keys(seen).sort();
  }

  var bar = document.getElementById("filters");
  SELECTS.forEach(function (s) {
    var sel = el("select");
    sel.appendChild(new Option("все", ""));
    uniq(s[0]).forEach(function (v) { sel.appendChild(new Option(v, v)); });
    state[s[0]] = "";
    sel.onchange = function () { state[s[0]] = sel.value; draw(); };
    bar.appendChild(field(s[1], sel));
  });
  var repo = el("input");
  repo.type = "search";
  repo.oninput = function () { state.repo = repo.value.toLowerCase(); draw(); };
  bar.appendChild(field("repo", repo));
  var since = el("input");
  since.type = "date";
  since.onchange = function () { state.since = since.value; draw(); };
  bar.appendChild(field("с даты", since));
  var unk = el("input");
  unk.type = "checkbox";
  unk.onchange = function () { state.unknown = unk.checked; draw(); };
  var unkLabel = el("label", "check");
  unkLabel.appendChild(unk);
  unkLabel.appendChild(document.createTextNode("показать пустые и неизвестные"));
  bar.appendChild(unkLabel);

  function keep(r) {
    if (r.hidden && !state.unknown) return false;
    for (var i = 0; i < SELECTS.length; i++) {
      var k = SELECTS[i][0];
      if (state[k] && r[k] !== state[k]) return false;
    }
    if (state.repo && (r.repo || "").toLowerCase().indexOf(state.repo) < 0) return false;
    return !(state.since && (r.started_at || "") < state.since);
  }

  function nest(rows, keys) {
    var tree = {};
    rows.forEach(function (r) {
      var node = tree;
      keys.slice(0, -1).forEach(function (k) { node = node[r[k] || DASH] = node[r[k] || DASH] || {}; });
      var last = r[keys[keys.length - 1]] || DASH;
      (node[last] = node[last] || []).push(r);
    });
    return tree;
  }

  function copyButton(text) {
    var b = el("button", "", "копировать");
    b.onclick = function () {
      function done() { b.textContent = "скопировано"; setTimeout(function () { b.textContent = "копировать"; }, 1500); }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, fallback);
      } else { fallback(); }
      function fallback() {
        var t = el("textarea");
        t.value = text;
        document.body.appendChild(t);
        t.select();
        try { document.execCommand("copy"); done(); } catch (e) { b.textContent = "не вышло"; }
        document.body.removeChild(t);
      }
    };
    return b;
  }

  function branchLine(b) {
    var line = (b.branch || DASH) + "  [" + (b.verdict || DASH) + "]  PR: " + (b.pr || DASH) + "  " + (b.files || DASH);
    return b.issues ? line + "  " + b.issues : line;
  }

  function session(s) {
    var d = el("div", "sess");
    d.appendChild(el("div", "meta", s.time + "  " + s.tool + (s.summary_source ? "  (" + s.summary_source + ")" : "")));
    d.appendChild(el("div", "summary", s.summary || DASH));
    var c = el("div", "cmd");
    c.appendChild(el("code", "", s.resume));
    c.appendChild(copyButton(s.resume));
    d.appendChild(c);
    return d;
  }

  function newest(list) { return list[0].started_at || ""; }

  function draw() {
    var rows = D.rows.filter(keep);
    var root = document.getElementById("tree");
    root.textContent = "";
    var tree = nest(rows, ["domain", "project", "repo", "branch"]);
    Object.keys(tree).sort().forEach(function (domain) {
      root.appendChild(el("div", "g1", domain));
      Object.keys(tree[domain]).sort().forEach(function (project) {
        root.appendChild(el("div", "g2", project));
        Object.keys(tree[domain][project]).sort().forEach(function (rp) {
          root.appendChild(el("div", "g3", rp));
          var branches = tree[domain][project][rp];
          Object.keys(branches).sort(function (a, b) {
            return newest(branches[b]) < newest(branches[a]) ? -1 : newest(branches[b]) > newest(branches[a]) ? 1 : 0;
          }).forEach(function (br) {
            root.appendChild(el("div", "g4 branch", branchLine(branches[br][0])));
            branches[br].forEach(function (s) { root.appendChild(session(s)); });
          });
        });
      });
    });
    document.getElementById("count").textContent = rows.length ? "сессий: " + rows.length : "нет сессий";
  }

  document.getElementById("footer").textContent = D.footer;
  draw();
})();
</script>
</body>
</html>
"""


def _row(r: dict) -> dict:
    cwd = r["cwd"] or r["worktree"] or ""
    return {
        "session_id": r["session_id"], "tool": r["tool"], "domain": r["domain"],
        "project": r["project"], "repo": r["repo"], "branch": r["branch"],
        "started_at": r["started_at"], "time": view._local_time(r["started_at"]),
        "verdict": r["verdict"], "pr": r["pr"], "pr_url": r["pr_url"], "files": r["files"],
        "issues": view._issues(r["issues"]), "summary": r["summary"],
        "summary_source": r["summary_source"],
        "resume": view.resume_command(r["tool"], r["session_id"], cwd),
        "hidden": r["origin"] != "live" or not r["user_msgs"],
    }


def render() -> str:
    found = view.rows(view.Filters(all=True))
    payload = {"rows": [_row(r) for r in found], "footer": view.footer()}
    # "<" as <: a summary holding "</script>" cannot close the data block.
    data = json.dumps(payload, ensure_ascii=False, default=str).replace("<", "\\u003c")
    return _TEMPLATE.replace("__DATA__", data)


def build(out: Path | None = None) -> Path:
    """Write the page to state/sessions.html, or to a path the caller named."""
    target = Path(out) if out is not None else paths.state_dir() / "sessions.html"
    store.replace(target, render(), place="state", dest=store.classify(target) != "state")
    return target
