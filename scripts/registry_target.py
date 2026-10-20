"""Validate explicit destination before building or exposing credentials."""
import os
import re

IMAGE = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?/[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+\Z")

def target(value):
    if not isinstance(value, str) or not IMAGE.fullmatch(value) or len(value) > 255:
        raise ValueError("REGISTRY_IMAGE must be a lowercase host/namespace/repository without tag")
    host = value.split("/", 1)[0]
    if "." not in host or any(not label or label.startswith("-") or label.endswith("-") for label in host.split(".")):
        raise ValueError("Invalid registry hostname")
    return host, value

if __name__ == "__main__":
    host, image = target(os.environ.get("REGISTRY_IMAGE", ""))
    with open(os.environ["GITHUB_ENV"], "a") as stream:
        stream.write(f"REGISTRY={host}\nIMAGE={image}\n")
