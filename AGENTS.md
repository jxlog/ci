# Generic image CI

This repository only builds, tests and publishes container images. Keep runtime deployment, registry consumers, platform integrations and private environment configuration outside this repository.

Use standard public GitHub runners, SHA-pinned official Actions, digest-pinned bases and explicit version tags. Never commit credentials or private build contexts. Use the repository owner's Git identity for authored changes.

Each logical change must describe Problem, Change, Validation, Limits and Milestone in its commit body. Keep published release identities stable; rewriting published history requires explicit owner approval.
