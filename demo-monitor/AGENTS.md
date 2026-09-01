dotworld is installed in this repo. Try dot --help to see commands.

## Comms — check in regularly

Before starting any work this session, read comms: `dot comms_read as=<your-name>`. Do this
again at the start of every task, at the end of every task, and at least every 5 minutes while
a task is in progress — whichever comes first. This is standard practice here, not optional.
`comms_read` with no `since` only returns what's new since your last read, so calling it often is
cheap.

## Workspaces — default on

Unless the user tells you otherwise, work in your own workspace: `dot workspace_open as=<your-name>`.
Land finished work with `dot workspace_submit message="..."`. If a submit or a plain `git merge`
leaves a `.dot.md` unreconciled, `dot sync_merge` repairs it property by property.

## dotworld

dotworld is installed on this host, and this repo is registered as a source
(on the CLI, `sourceId` is inferred from your working directory). It works with
git, not around it.

**dotworld has features, not rules.** How this repo uses them is for you and the
maintainer to decide. What follows is what the pieces are and a few conventions
that tend to work — not a protocol to comply with.

**Every file can have a dot.** Beside a file,
`.dotworld/dots/<path>.dot.md` holds what dotworld knows about it: title, tags,
a summary, an authorable body, and any properties you define. It appears on the
first write that records something, and on `dot file_create`, which authors a
file and its dot together. A file with no dot is indexed and searchable all the
same. The source file is never touched.

Properties are how you record state. Declare one with the merge strategy that
fits — `dot property_register name=review_status merge=last-writer
description="..."` — then `dot property_set`, and read it back with
`dot search_properties where='{"review_status":"pending"}'`. `merge=counter`
sums each branch's own change, so a property can carry a count across parallel
work.

**Summaries compound.** A summary is stamped against the body it describes, so
it reports itself `unread`, `current` or `stale`. Kept current, they make
`dot search_semantic query="..."` worth reaching for before reading files, and
`dot dot_get` can answer from metadata alone.

Invent your own uses. It is all in git, and it is yours to break — play by git's
rules and you will be fine. We can always roll back.

`dot --help` for the command set. After adding or renaming files,
`dot sync_source` reindexes them — it mints no dots, because a file gets one
only once there is something to record about it. Something broken or missing?
https://github.com/DragonLord-64/dotworld-releases/issues
