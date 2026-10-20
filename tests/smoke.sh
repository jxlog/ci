#!/usr/bin/env bash
set -euo pipefail
image=${1:?usage: smoke.sh IMAGE}
[[ $(docker image inspect --format '{{.Config.User}}' "$image") == 65532:65532 ]]
result=$(timeout 30 docker run --rm --network none --read-only --cap-drop ALL   --security-opt no-new-privileges "$image")
[[ "$result" == "$(cat image/message.txt)" ]]
timeout 30 docker run --rm --network none --read-only --cap-drop ALL   --security-opt no-new-privileges --entrypoint /bin/sh "$image" -ec   'test "$(id -u)" = 65532; test -r /message.txt; test ! -w /; test -x /bin/cat'
echo 'PASS: payload, entrypoint, non-root user, restricted container execution'
