# Upstream port baseline

This fork diverged permanently from [imbue-ai/sculptor](https://github.com/imbue-ai/sculptor)
at `d457af55b2`. Upstream changes are consumed only by selective porting
(see the `port-upstream` skill), never by merging `upstream/main`.

**Last triaged upstream commit: `dbcf5ac8`** (imbue-ai/sculptor PR #246).

`git log --first-parent --oneline <baseline>..upstream/main` lists what has
not been triaged. Porting sessions advance the baseline; the per-session
record of what was ported or skipped lives in each porting PR's description
(ported commits carry the upstream SHA via `cherry-pick -x` or a
`Port upstream #N` title, so `git log --grep` recovers the full history).
