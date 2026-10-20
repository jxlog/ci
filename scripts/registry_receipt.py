"""Read authenticated registry metadata on the runner; never download layers.

Docker owns registry authentication. Raw manifest hashes are independently
verified before a publication receipt can be emitted.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from registry_target import target

DIGEST = re.compile(r"sha256:[a-f0-9]{64}\Z")
TAG = re.compile(r"(?:v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)|build-[a-z0-9-]{1,80})\Z")
MAX_MANIFEST = 4 * 1024 * 1024

def require(condition, message):
    if not condition:
        raise ValueError(message)

def decoded(raw, digest):
    require(isinstance(digest, str) and DIGEST.fullmatch(digest), "Invalid manifest digest")
    require(len(raw) <= MAX_MANIFEST, "Manifest too large")
    # Buildx may append one display newline. Never reserialize JSON for hashing.
    candidates = [raw, raw[:-1]] if raw.endswith(b"\n") else [raw]
    matches = [value for value in candidates if "sha256:" + hashlib.sha256(value).hexdigest() == digest]
    require(len(matches) == 1, "Registry manifest digest mismatch")
    value = json.loads(matches[0])
    require(isinstance(value, dict) and value.get("schemaVersion") == 2, "Unsupported manifest")
    return value

def manifest(image, digest, runner=subprocess.run, sleep=time.sleep):
    target(image)
    require(isinstance(digest, str) and DIGEST.fullmatch(digest), "Invalid manifest digest")
    for attempt in range(3):
        try:
            result = runner(["docker", "buildx", "imagetools", "inspect", "--raw", image + "@" + digest],
                            capture_output=True, timeout=90)
            if result.returncode == 0:
                return decoded(result.stdout, digest)
        except subprocess.TimeoutExpired:
            pass
        if attempt < 2:
            sleep(2 ** (attempt + 1))
    # Do not include CLI stderr, credentials, response bodies or token URLs.
    raise RuntimeError("Registry manifest observation failed after three bounded reads")

def verified_metadata(image, digest, read=manifest):
    value = read(image, digest)
    platform_digest = digest
    if "manifests" in value:
        candidates = [item for item in value["manifests"]
                      if item.get("platform", {}).get("os") == "linux"
                      and item.get("platform", {}).get("architecture") == "amd64"]
        require(len(candidates) == 1, "Expected exactly one linux/amd64 manifest")
        platform_digest = candidates[0]["digest"]
        value = read(image, platform_digest)
    layers = value.get("layers")
    require(isinstance(layers, list) and len(layers) <= 1000, "Invalid layers")
    for layer in layers:
        require(isinstance(layer, dict) and DIGEST.fullmatch(layer.get("digest", ""))
                and type(layer.get("size")) is int and layer["size"] >= 0, "Invalid layer descriptor")
    config = value.get("config")
    require(isinstance(config,dict) and DIGEST.fullmatch(config.get("digest", ""))
            and type(config.get("size")) is int and config["size"] >= 0, "Invalid config descriptor")
    return {"digest": digest, "platform_digest": platform_digest, "config_digest": config["digest"], "platform": "linux/amd64",
            "compressed_layer_bytes": sum(layer["size"] for layer in layers), "layers": len(layers),
            "registry_manifest_integrity": "passed"}

def main():
    image = os.environ["IMAGE"]
    tag = os.environ["GITHUB_REF_NAME"]
    require(TAG.fullmatch(tag), "Invalid publication tag")
    commit = os.environ["GITHUB_SHA"]
    require(re.fullmatch("[a-f0-9]{40}", commit), "Invalid pipeline commit")
    spec = json.loads(os.environ.get("BUILD_SPEC", "null"))
    image_tag = spec["image_tag"] if spec else tag
    require(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", image_tag), "Invalid image tag")
    run_id, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    require(re.fullmatch("[1-9][0-9]*", run_id) and re.fullmatch("[1-9][0-9]*", attempt), "Invalid run identity")
    workflow_ref = os.environ["GITHUB_WORKFLOW_REF"]
    workflow_path = workflow_ref.split("@",1)[0].removeprefix(os.environ["GITHUB_REPOSITORY"]+"/")
    require(re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml",workflow_path), "Invalid workflow identity")
    context_sha = os.environ.get("SOURCE_CONTEXT_SHA256") if spec else None
    require(spec is None or re.fullmatch(r"[a-f0-9]{64}",context_sha or ""), "Missing context snapshot")
    receipt = {"schema_version": 1, "repository": os.environ["GITHUB_REPOSITORY"],
               "workflow_path": workflow_path, "source_context_sha256": context_sha,
               "source_context_scope": "entire_context_except_git_metadata_including_ignored_files" if spec else None,
               "pipeline_commit": commit, "trigger_tag": tag, "run_id": int(run_id),
               "run_attempt": int(attempt), "image": image, "image_tag": image_tag,
               "request": spec, "runtime_test": os.environ.get("RUNTIME_TEST", "not_performed"),
               **verified_metadata(image, os.environ["DIGEST"])}
    name = f"receipt-{image_tag}-{run_id}-{attempt}.json"
    Path(name).write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
        stream.write("receipt=" + name + "\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
        stream.write("### Verified registry publication\n```json\n" + json.dumps(receipt, indent=2) + "\n```\n")
    print("BUILD_RECEIPT_JSON=" + json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    main()
