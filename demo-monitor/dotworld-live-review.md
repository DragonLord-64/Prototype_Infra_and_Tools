# DotWorld live-test notes — grafana-agent

Working session: building Grafana config for demo-monitor alongside 3 other
concurrent agents (prometheus-agent, server-container, switch-container).

## Worked well
- `comms_read`/`comms_send` were the MVP of this session — cheap, and the
  only reason 4 concurrent agents didn't collide on container names/ports/
  network. No errors, no friction.
- `workspace_open` + `workspace_submit` landed cleanly both times, and
  correctly reported which branch it actually merged into.

## Friction / rough edges
- **`summary_refresh` doesn't author a first summary.** It only rewrites a
  *stale* summary; a freshly-written body stays `unread` forever unless you
  discover you can set `properties.summary=...` directly via `dot_set`. This
  isn't documented anywhere obvious — I found it by inspecting a `dot_set`
  response and noticing `summary` was just another property.
- **Empty workspaces have no memory of sibling in-progress work.** Since
  `demo-monitor/` was untracked in git, every agent's `workspace_open`
  started from a totally empty folder — even though the shared checkout
  already had real (uncommitted) files from other agents. This produced
  exactly the "no common ancestor" problem another agent flagged in comms:
  independent branches all inventing overlapping scaffolding.
- **`dot_get ... fields=["summaryStatus"]` silently printed nothing** — no
  error, just an empty row. Had to fall back to an unfiltered `dot_get` to
  eyeball `summary`/`summary_blob` instead.
- Two of the four agents skipped `workspace_open` entirely (editing the
  shared checkout directly, per their own users' instructions) — isolation
  is opt-in, not enforced, so it only works if everyone actually uses it.

# DotWorld live-test notes — prometheus-agent

## Worked well
- `comms_send`/`comms_read` again — cheap, easy to poll, and it's the only
  reason 4-5 concurrent agents didn't step on each other's ports/network/
  container names.
- Property registry validation caught my mistakes with clear, actionable
  errors instead of silently writing bad metadata.

## Errors I hit calling commands
- `dot dot_get path=demo-monitor/README.md` → `unknown param: path — dot_get
  accepts sourceId, files, index, fields, workspace`. Wrong param name; it's
  `files` (an array), not `path`.
- `dot property_set properties.summary="..."` → `unknown param:
  properties.summary`. I used `dot_set`'s dotted-object shorthand
  (`properties.<key>=<value>`) on `property_set`, which instead wants plain
  `key=`/`value=`. Easy mixup between two similarly-shaped commands.
- Same `summary_refresh`-doesn't-author-a-first-summary gap grafana-agent
  found above — I hit it independently and also had to discover
  `property_set key=summary value=...` by reading `property_list`'s output
  rather than from any command's own docs.

## Friction, not a command error
- Started in my own `workspace_open`'d branch per AGENTS.md, but since
  `demo-monitor/` wasn't committed anywhere, my workspace started empty —
  no visibility into the other agents' in-progress files. Once it was clear
  the team had converged on editing the shared checkout directly, I had to
  migrate my own files out of the workspace to match.

## server-container

- **`comms_send` param names don't match `comms_read`'s.** First attempt used
  `as=`/`message=` (mirroring `comms_read`) and got
  `unknown params: as, message`; real params are `from`, `to`, `topic`,
  `body` — `topic` is required, only surfaced on the second error.
- **File paths for `dot_set`/`property_set` are relative to the source root,
  not cwd.** Working from inside `demo-monitor/` (a subfolder of the
  `Prototype` source) and passing `file=demo-monitor/server/Dockerfile`
  doubled the prefix: `no file at demo-monitor/demo-monitor/server/Dockerfile`.
  Needed `file=server/Dockerfile`.
- Hit the same empty-workspace-worktree and unread-summary issues
  grafana-agent already wrote up above — seconding both.
- Once the params were right, `dot_set`/`property_set`/`comms_read` all
  behaved exactly as documented.

## switch-container

- **Not a dotworld bug, but worth flagging: my own shell quoting mangled a
  `comms_send` body twice.** I put backticked inline-code spans inside a
  double-quoted bash string; bash ran them as real command substitution.
  One dropped text silently, the other actually executed `docker compose
  up --scale switch=N` for real (harmlessly failed on the literal `N`,
  verified via `docker ps`/`docker network ls` afterward — no side effect,
  but it could have been worse). Fix was just: no backticks in a
  double-quoted `dot comms_send body="..."`, or use single quotes.
- Same doubled-path issue server-container hit: `dot dot_set`/`file_read`
  paths are relative to the source root, not cwd — from inside
  `demo-monitor/`, `file=demo-monitor/switch/exporter.py` doubled to
  `demo-monitor/demo-monitor/switch/exporter.py: no file at...`. Needed
  `file=switch/exporter.py`.
- `comms_send sourceId=Prototype_Infra_and_Tools` → `unknown source`. The
  registered id is the short name (`Prototype`), not the directory name;
  had to run `source_list` to find it.
- `workspace_submit as=switch-container` → `unknown param: as`. It infers
  identity from cwd being inside the workspace worktree; had to `cd` into
  the worktree first, then call it with no identity param at all.
- `file_read paths=[...]` → `unknown param: paths`; correct param is
  `files`. `file_tree path=demo-monitor` → `unknown param: path`;
  `file_tree` takes no path filter at all, just `root`/`depth`/`workspace`.
- Same `summary_refresh` gap as above: three brand-new dots all came back
  `skipped.unstamped`, summary still the `unread` placeholder. Had to set
  `properties.summary=...` directly via `dot_set` — which *did* also
  compute and stamp `summary_blob` automatically, so the docs' "do not set
  it by hand" warning is about the blob specifically, not the summary text.
- Confirms the empty-workspace problem everyone above hit: my
  `workspace_open` branch had none of the other agents' in-flight
  `demo-monitor/` work, since none of it was committed to git yet.
