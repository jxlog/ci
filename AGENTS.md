# CI repository

Keep this a generic tag-triggered image build/publish pipeline. No benchmark-specific production conditions. Development, Git and Host verification run on the authorized Host. Local files are only SSH script payloads or public report copies.

Do not commit credentials, private build contexts, signed URLs or Host paths. Use standard public GitHub runners only; no new paid cloud resources or Inspire compute without a new user budget. Do not resume the paused Harbor automation.

Each logical change needs a commit body containing Problem, Change, Validation, Limits and Milestone. Preserve published tags/history. Record real CI runs and digest-bound tests separately from untested Inspire import.
