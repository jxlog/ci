import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from registry_target import target
from registry_receipt import decoded, manifest, verified_metadata
from publish_receipt import GitHub

def data(value):
    raw = json.dumps(value).encode()
    return raw, "sha256:" + hashlib.sha256(raw).hexdigest()

class PublicationTests(unittest.TestCase):
    def test_destination_rejects_tag_credentials_shell_and_missing_config(self):
        self.assertEqual(target("registry.example.com/team/image"), ("registry.example.com", "registry.example.com/team/image"))
        for value in ("", "https://registry.example.com/team/image", "user:pass@registry.example.com/team/image",
                      "registry.example.com/team/image:tag", "registry.example.com/team/../image", "x\nIMAGE=other"):
            with self.subTest(value=value), self.assertRaises(ValueError):target(value)

    def test_raw_digest_and_display_newline(self):
        raw,digest=data({"schemaVersion":2,"layers":[]})
        self.assertEqual(decoded(raw,digest),decoded(raw+b"\n",digest))
        with self.assertRaises(ValueError):decoded(raw+b" ",digest)

    def test_bounded_reads_no_push_and_no_credential_output(self):
        raw,digest=data({"schemaVersion":2,"layers":[]})
        calls=[]
        def runner(args,**kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=1 if len(calls)<3 else 0,stdout=raw,stderr=b"secret")
        self.assertEqual(manifest("registry.example.com/team/image",digest,runner,lambda _:None)["schemaVersion"],2)
        self.assertEqual(len(calls),3)
        self.assertTrue(all(call[:5]==["docker","buildx","imagetools","inspect","--raw"] for call in calls))

    def test_index_selects_runtime_manifest_ignoring_attestation(self):
        child="sha256:"+"a"*64
        image={"schemaVersion":2,"layers":[{"digest":"sha256:"+"b"*64,"size":700}]}
        index={"schemaVersion":2,"manifests":[{"digest":child,"platform":{"os":"linux","architecture":"amd64"}},
               {"digest":"sha256:"+"c"*64,"platform":{"os":"unknown","architecture":"unknown"}}]}
        root="sha256:"+"d"*64
        result=verified_metadata("registry.example.com/team/image",root,lambda _,d:index if d==root else image)
        self.assertEqual(result["platform_digest"],child)
        self.assertEqual(result["compressed_layer_bytes"],700)
        index["manifests"].append(index["manifests"][0])
        with self.assertRaises(ValueError):verified_metadata("registry.example.com/team/image",root,lambda *_:index)

    def test_negative_or_non_integer_layer_size_rejected(self):
        for size in (-1,True,"2"):
            with self.assertRaises(ValueError):
                verified_metadata("registry.example.com/team/image","sha256:"+"a"*64,
                    lambda *_:{"schemaVersion":2,"layers":[{"digest":"sha256:"+"b"*64,"size":size}]})

    def test_existing_receipt_must_match_content_digest(self):
        raw=b'{"ok":true}\n'
        valid={"state":"uploaded","size":len(raw),"digest":"sha256:"+hashlib.sha256(raw).hexdigest()}
        GitHub.verify_asset(valid,raw)
        with self.assertRaises(RuntimeError):GitHub.verify_asset({**valid,"digest":"sha256:"+"a"*64},raw)

    def test_unknown_upload_is_observed_not_replayed(self):
        class Fake(GitHub):
            def __init__(self):self.posts=0;self.reads=0
            def find_asset(self,*args):
                self.reads+=1
                if self.reads==1:return None
                return {"state":"uploaded","size":2,"digest":"sha256:"+hashlib.sha256(b"{}").hexdigest(),
                        "browser_download_url":"https://github.com/o/r/releases/download/v1.0.0/r.json"}
            def request(self,*args,**kwargs):self.posts+=1;raise TimeoutError()
        api=Fake()
        api.publish({"id":1},"r.json",b"{}")
        self.assertEqual(api.posts,1)
        self.assertEqual(api.reads,2)

if __name__=="__main__":unittest.main()
