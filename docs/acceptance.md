# Image CI acceptance

## v0.1.0 — passed

- Source: `18be22e76f4537ac6f43fa2c59197b959e43db5d`.
- [Actions run 39365439643](https://github.com/jxlog/ci/actions/runs/39365439643), attempt 1, success.
- Standard `ubuntu-24.04` runner; release job ran from 2026-10-20 03:39:29 UTC to 03:39:49 UTC (20 seconds).
- Passed: tag validation, build, non-root/read-only/network-disabled container tests, GHCR publication, published-digest pull, repeated container tests and source revision comparison.
- [Container package](https://github.com/jxlog/ci/pkgs/container/ci): public when checked.

## Milestones

| Milestone | Status | Evidence |
|---|---|---|
| CI-1: tag-only workflow and pinned inputs | Passed | Workflow and first successful tag run |
| CI-2: build, test and publish | Passed | v0.1.0 run above |

## Scope and limits

Only `linux/amd64` and the small sample image were tested. Large images, other architectures, downstream consumers and registry outage recovery are not qualified by this result. No persistent build cache or build-record artifact is configured.

The original commit and tag are preserved. Current documentation describes a generic image publisher. New commits use the repository owner's GitHub-associated author identity. A subsequent version records the current documentation and source revision without changing existing release identities.
