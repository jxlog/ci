"""Publish a durable metadata-only signal using the workflow's scoped token.

Never overwrite an existing receipt. A timed-out create/upload is reconciled by
reading its deterministic identity; it is not blindly repeated.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class GitHub:
    def __init__(self, repo, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("Invalid repository")
        self.prefix = "/repos/" + repo
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, data=None, upload=False):
        host = "uploads.github.com" if upload else "api.github.com"
        headers = {"Authorization": "Bearer " + self.token, "User-Agent": "generic-image-ci",
                   "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "Content-Type": "application/json"}
        request = urllib.request.Request("https://" + host + self.prefix + path,
                                         data=data, headers=headers, method=method)
        with self.opener.open(request, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("GitHub response too large")
            return json.loads(raw)

    def get(self, path, absent_ok=False):
        for attempt in range(4):
            try:
                return self.request("GET", path)
            except urllib.error.HTTPError as error:
                if error.code == 404 and absent_ok:
                    return None
                if error.code not in (408, 429, 500, 502, 503, 504):
                    raise RuntimeError("GitHub read rejected: HTTP " + str(error.code)) from None
            except (urllib.error.URLError, OSError):
                pass
            if attempt < 3:
                time.sleep(2 ** attempt)
        raise RuntimeError("GitHub observation unavailable")

    def ensure_release(self, tag, commit):
        path = "/releases/tags/" + urllib.parse.quote(tag, safe="")
        release = self.get(path, absent_ok=True)
        if release is None:
            body = {"tag_name": tag, "target_commitish": commit, "name": "Image publication " + tag,
                    "body": "Machine-readable publication receipts. Image data stays in the configured registry.",
                    "draft": False, "prerelease": True, "make_latest": "false"}
            try:
                self.request("POST", "/releases", json.dumps(body).encode())
            except (urllib.error.URLError, OSError):
                pass  # Possible success or parallel winner: observe; never repeat POST.
            for _ in range(4):
                release = self.get(path, absent_ok=True)
                if release is not None:
                    break
                time.sleep(2)
        if not release or release.get("tag_name") != tag or release.get("draft"):
            raise RuntimeError("Release create outcome unconfirmed; reconcile before another run")
        # The trigger tag is already required to exist. No tag is moved here.
        if release.get("target_commitish") != commit:
            raise RuntimeError("Existing release commit differs from this pipeline")
        return release

    def find_asset(self, release_id, name):
        matches = []
        for page in range(1, 5):
            rows = self.get(f"/releases/{release_id}/assets?per_page=100&page={page}")
            matches.extend(item for item in rows if item.get("name") == name)
            if len(rows) < 100:
                break
        if len(matches) > 1:
            raise RuntimeError("Duplicate publication asset")
        return matches[0] if matches else None

    @staticmethod
    def verify_asset(asset, raw):
        expected = "sha256:" + hashlib.sha256(raw).hexdigest()
        if (asset.get("state") != "uploaded" or asset.get("size") != len(raw)
                or asset.get("digest") != expected):
            raise RuntimeError("Existing publication asset is incomplete or differs; never overwrite")

    def publish(self, release, name, raw):
        identifier = release["id"]
        asset = self.find_asset(identifier, name)
        if asset is None:
            try:
                self.request("POST", f"/releases/{identifier}/assets?name=" + urllib.parse.quote(name),
                             raw, upload=True)
            except (urllib.error.URLError, OSError):
                pass
            for _ in range(4):
                asset = self.find_asset(identifier, name)
                if asset is not None:
                    break
                time.sleep(2)
        if asset is None:
            raise RuntimeError("Receipt upload outcome unconfirmed; no automatic replay")
        self.verify_asset(asset, raw)
        return asset["browser_download_url"]

def main():
    path = Path(sys.argv[1])
    if not re.fullmatch(r"receipt-[A-Za-z0-9_.-]+\.json", path.name) or path.name != str(path):
        raise ValueError("Invalid receipt filename")
    raw = path.read_bytes()
    if len(raw) > 128 * 1024:
        raise ValueError("Receipt too large")
    receipt = json.loads(raw)
    expected = {"repository": os.environ["GITHUB_REPOSITORY"],
                "pipeline_commit": os.environ["GITHUB_SHA"],
                "trigger_tag": os.environ["GITHUB_REF_NAME"],
                "run_id": int(os.environ["GITHUB_RUN_ID"]),
                "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"])}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Receipt identity mismatch")
    api = GitHub(expected["repository"], os.environ["GH_TOKEN"])
    release = api.ensure_release(expected["trigger_tag"], expected["pipeline_commit"])
    url = api.publish(release, path.name, raw)
    print("PUBLICATION_RECEIPT=" + url)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not print token-bearing request objects or remote bodies.
        print("Receipt publication failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
