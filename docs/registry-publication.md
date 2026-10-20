# Registry publication acceptance

Problem: image storage and the completion signal were coupled to one registry
and transient workflow logs.

Change: select an explicit registry through repository configuration, use its
login for push and manifest verification, and publish immutable metadata-only
release assets. No consumer-specific behavior lives in this repository.

Validation: protocol tests reject unsafe destinations, changed manifests,
ambiguous platforms and incorrect existing receipts; a simulated lost upload
response is reconciled without another upload.

Limits: live push and consumer acceptance remain pending configuration and an
actual workflow run. A private registry requires consumer-side credentials.

Milestone: registry-neutral publication and recoverable completion signal.
