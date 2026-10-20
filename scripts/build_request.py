"""Validate public build requests carried by immutable annotated Git tags."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

FIELDS = {'repository', 'revision', 'context', 'dockerfile', 'dockerfile_sha256'}


def relative_path(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise ValueError('invalid relative path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError('path must be normalized and stay within source')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', value):
        raise ValueError('unsupported path characters')
    return value


def plan(raw, pipeline):
    if len(raw.encode()) > 65536:
        raise ValueError('request exceeds 64 KiB')
    if not re.fullmatch(r'[a-f0-9]{40}', pipeline):
        raise ValueError('pipeline must be pinned to a commit')
    data = json.loads(raw)
    if set(data) != {'version', 'images'} or data['version'] != 1:
        raise ValueError('unsupported request schema')
    if not isinstance(data['images'], list) or not 1 <= len(data['images']) <= 128:
        raise ValueError('request must contain 1..128 images')
    rows, seen = [], set()
    for item in data['images']:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError('unexpected image fields')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', item['repository']):
            raise ValueError('repository must be owner/name')
        if not re.fullmatch(r'[a-f0-9]{40}', item['revision']):
            raise ValueError('source revision must be a full commit SHA')
        if not re.fullmatch(r'[a-f0-9]{64}', item['dockerfile_sha256']):
            raise ValueError('missing Dockerfile integrity pin')
        relative_path(item['context']); relative_path(item['dockerfile'])
        canonical = json.dumps(item, sort_keys=True, separators=(',', ':'))
        if canonical in seen:
            raise ValueError('duplicate image request')
        seen.add(canonical)
        key = hashlib.sha256((pipeline + '\n' + canonical).encode()).hexdigest()[:32]
        rows.append({**item, 'key': key, 'image_tag': 'build-' + key})
    return {'include': rows}


def verify_source(spec, root):
    root = Path(root).resolve()
    current = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if current != spec['revision']:
        raise ValueError('checked out revision differs from request')
    context = (root / relative_path(spec['context'])).resolve()
    dockerfile = (context / relative_path(spec['dockerfile'])).resolve()
    if not context.is_relative_to(root) or not dockerfile.is_relative_to(context):
        raise ValueError('symlink escapes source/context')
    if not context.is_dir() or not dockerfile.is_file():
        raise ValueError('context or Dockerfile missing')
    if hashlib.sha256(dockerfile.read_bytes()).hexdigest() != spec['dockerfile_sha256']:
        raise ValueError('Dockerfile differs from reviewed public source')
    return {'context': str(context), 'file': str(dockerfile)}


def read_tag(ref, pipeline, cwd=None):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()
    if git('cat-file', '-t', ref) != 'tag':
        raise ValueError('request requires an annotated tag')
    if git('rev-parse', ref + '^{commit}') != pipeline:
        raise ValueError('request tag differs from event commit')
    return git('for-each-ref', '--format=%(contents)', ref)


def main():
    if sys.argv[1] == 'plan':
        ref = os.environ['GITHUB_REF']
        if not re.fullmatch(r'refs/tags/build-[a-z0-9-]{1,80}', ref):
            raise ValueError('unsupported request tag')
        raw = read_tag(ref, os.environ['GITHUB_SHA'])
        result = {'matrix': json.dumps(plan(raw, os.environ['GITHUB_SHA']), separators=(',', ':'))}
    else:
        result = verify_source(json.loads(os.environ['BUILD_SPEC']), '_source')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        for key, value in result.items():
            output.write(f'{key}={value}\n')


if __name__ == '__main__':
    main()
