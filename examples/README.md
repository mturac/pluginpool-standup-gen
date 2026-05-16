# standup-gen — examples

Each scenario shows: a starting state, the exact command, the markdown the helper produces, and what Claude can layer on top.

---

## Scenario 1 — single repo, last business day

**Setup:** It's Monday morning. Friday you made three commits to the `api` repo.

```
$ git -C ~/work/api log --oneline --since=2026-05-15
3313ef1 feat: change 3
373dec1 feat: change 2
0070d08 feat: change 1
```

**Command:**

```sh
python3 scripts/standup.py --format md
```

**Helper output (verbatim, captured from a hermetic test repo):**

```markdown
# Standup — 2026-05-16

## Yesterday
### api
- 2026-05-15 `3313ef1` feat: change 3
- 2026-05-15 `373dec1` feat: change 2
- 2026-05-15 `0070d08` feat: change 1

## Today (planned)
- TODO

## Blockers
- TODO
```

**What Claude does next** (running `/standup-gen`):

```markdown
# Standup — 2026-05-16

## Yesterday
- Shipped three iterative changes to the api service (Friday)

## Today (planned)
- Open a PR for the in-flight work
- Pair with @reviewer on the rate-limiting design

## Blockers
- None
```

Claude can compress duplicate-feeling commits, lift in-flight work from your unpushed branch, and propose specific Today items.

---

## Scenario 2 — multiple repos

You split work across two repos:

```sh
python3 scripts/standup.py --repos /work/api,/work/web --format md
```

The "Yesterday" section gets one sub-section per repo so it's clear which work happened where.

---

## Scenario 3 — different date range

Coming back from a long weekend:

```sh
python3 scripts/standup.py --since 2026-05-11 --until none --format md
```

`--until none` removes the default "today 00:00" upper bound when you want everything up to right now.

---

## Scenario 4 — different author (e.g. summarising a teammate's week)

```sh
python3 scripts/standup.py --author teammate@company.com --since 2026-05-11 --format json
```

Useful for a tech lead or manager prepping a 1:1.

---

## The date-bound guarantee

The most important behaviour to know: by default, `--until` is set to **today 00:00**, exclusive. This is intentional — without it, "yesterday" would silently include today's in-progress work, which is confusing for the audience of a standup.

The test `test_default_until_excludes_today` enforces this. Use `--until none` only when you want to include today.
