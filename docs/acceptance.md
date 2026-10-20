# Image CI acceptance

## Batch cold builds — infrastructure passed

- Pipeline commit: `488096db2465c0cc145e808b427bfdaa16ef323b`; standard public `ubuntu-24.04` runners only.
- Four immutable annotated-tag requests exercised 97 unchanged public build contexts; **94 images built, published and passed independent anonymous manifest/config/source-label verification**.
- Largest published image: **13.63 GiB** of compressed layers.
- **3 original inputs failed**. Failure classes: upstream_git_source_unavailable_anonymously (1), upstream_apt_package_404 (2). These original task/source issues are recorded without remediation and are outside infrastructure acceptance. Their original job failures remain unchanged.
- The initial request failed before building because checkout replaced a local annotated tag with its peeled commit. An independent fix now preserves the tag and binds it to the event commit; nine regression tests pass.
- [Machine-readable evidence and all run links](batch-2026-10-19.json).
- No large-image runtime or downstream deployment qualification is claimed.

## v0.1.1 — passed

- Source: `1f85ace3f6db4330d65acb9d62ce945ae838e7c2`; GitHub author: `jxlog` (Jiangxuan Long).
- [Actions run 39365973101](https://github.com/jxlog/ci/actions/runs/39365973101), attempt 1, success.
- Standard `ubuntu-24.04` runner; release job duration **26 seconds**.
- Pre-publication container tests, GHCR publication, published-digest pull, repeated runtime tests and source revision comparison all passed.
- Public registry manifest bytes independently matched the published digest.
- Image: `ghcr.io/jxlog/ci@sha256:e8cca9f3db1bff3eaea14ac125a9a708b2302076cc8eeff01d33a8031591cd89`.
- Machine-readable evidence: [v0.1.1.json](v0.1.1.json).

## v0.1.0 — passed

- Source: `18be22e76f4537ac6f43fa2c59197b959e43db5d`.
- [Actions run 39365439643](https://github.com/jxlog/ci/actions/runs/39365439643), attempt 1, success.
- Standard `ubuntu-24.04` runner; release job ran from 2026-10-20 03:39:29 UTC to 03:39:49 UTC (20 seconds).
- Passed: tag validation, build, non-root/read-only/network-disabled container tests, GHCR publication, published-digest pull, repeated container tests and source revision comparison.
- [Container package](https://github.com/jxlog/ci/pkgs/container/ci): public when checked.

## Milestones

| Milestone | Status | Evidence |
|---|---|---|
| CI-1: tag-only workflow and pinned inputs | Passed | Workflow and both successful tag runs |
| CI-2: build, test and publish | Passed | v0.1.0 and v0.1.1 runs above |
| CI-3: large public context builds | Passed for build/publication; task-source issues tracked separately | Batch cold-build evidence above |

## Scope and limits

Only `linux/amd64` was tested. The small sample has runtime checks; the large-image sweep qualifies build and publication for successful inputs only. Other architectures, downstream consumers, large-image runtime behavior and registry outage recovery remain unqualified. No persistent build cache or build-record artifact is configured.

The original commit and tag are preserved. Current documentation describes a generic image publisher. New commits use the repository owner's GitHub-associated author identity. Version v0.1.1 records the corrected documentation and owner identity without changing the first release.
