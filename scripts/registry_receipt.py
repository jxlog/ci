"""Read back a public OCI index and platform manifest without registry credentials."""
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request


def main():
    image = os.environ['IMAGE']
    digest = os.environ['DIGEST']
    if not re.fullmatch(r'ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+', image):
        raise ValueError('expected a GHCR repository')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('expected published digest')
    repository = image.removeprefix('ghcr.io/')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('https://ghcr.io/token?service=ghcr.io&scope=repository:'+repository+':pull', timeout=30) as response:
        token = json.load(response)['token']
    def manifest(ref):
        headers = {'Authorization': 'Bearer '+token, 'Accept': 'application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json'}
        with opener.open(urllib.request.Request('https://ghcr.io/v2/'+repository+'/manifests/'+ref, headers=headers), timeout=30) as response:
            body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024 or 'sha256:'+hashlib.sha256(body).hexdigest() != ref:
            raise ValueError('registry manifest integrity mismatch')
        return json.loads(body)
    index = manifest(digest)
    if 'manifests' in index:
        child = next(e for e in index['manifests'] if e.get('platform', {}).get('architecture') == 'amd64' and e.get('platform', {}).get('os') == 'linux')
        platform_digest = child['digest']; data = manifest(platform_digest)
    else:
        platform_digest = digest; data = index
    receipt = {'image': image+'@'+digest, 'platform': 'linux/amd64', 'platform_digest': platform_digest, 'compressed_layer_bytes': sum(e['size'] for e in data['layers']), 'layers': len(data['layers']), 'request': json.loads(os.environ['BUILD_SPEC']), 'pipeline_commit': os.environ['GITHUB_SHA'], 'registry_manifest_integrity': 'passed', 'runtime_test': 'not_performed'}
    print('BUILD_RECEIPT_JSON='+json.dumps(receipt, sort_keys=True))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
        output.write('### Published image\n\n```json\n'+json.dumps(receipt, indent=2)+'\n```\n')


if __name__ == '__main__':
    main()
