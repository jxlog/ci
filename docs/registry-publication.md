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


Live probe v0.2.0 built and tested the sample, authenticated successfully and
uploaded its layers, but publication failed while sending BuildKit's automatic
attestation (`unknown manifest class for application/vnd.oci.empty.v1+json`).
Both workflows now explicitly disable provenance/SBOM attachments, producing
the regular runtime image without requiring OCI attestation support. Digest
verification and metadata receipts remain enabled; these are not signed SLSA
provenance. The failed tag is retained. v0.2.1 is a new compatibility probe.


## Additive artifact identity fields

Context publications now bind `source_context_sha256`, `source_context_scope`,
`workflow_path`, and the runtime `config_digest`. Existing schema 1 receipts
remain historical records. Consumers requiring these fields must reject older
receipts that do not carry them; they must not infer a config ID from an index.

The context snapshot conservatively includes ignored files and excludes Git
metadata. It records regular-file bytes, executable bits, directory names and
non-escaping symlink targets. It is not Docker's filtered build-context tar hash.
The source revision and original Dockerfile hash remain immutable request inputs.
Automatic provenance/SBOM attachments remain disabled for registry compatibility;
an ordinary completion receipt is not a signed provenance claim.
