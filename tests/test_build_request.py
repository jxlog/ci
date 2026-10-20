import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_request import plan, verify_source

class RequestTests(unittest.TestCase):
    def setUp(self):
        self.item = {'repository': 'owner/source', 'revision': 'a'*40, 'context': 'image', 'dockerfile': 'Dockerfile', 'dockerfile_sha256': hashlib.sha256(b'FROM scratch\n').hexdigest()}
    def make(self, item=None, pipeline='b'*40):
        return plan(json.dumps({'version': 1, 'images': [item or self.item]}), pipeline)
    def test_stable_identity_bound_to_pipeline_and_source(self):
        self.assertEqual(self.make(), self.make())
        self.assertNotEqual(self.make(), self.make(pipeline='c'*40))
        other={**self.item,'revision':'d'*40};self.assertNotEqual(self.make(),self.make(other))
    def test_path_escape_and_shell_inputs_rejected(self):
        for path in ['../secret','/etc','image/../other','image\ncommands','image;id','./image','image//sub']:
            with self.subTest(path=path),self.assertRaises(ValueError):self.make({**self.item,'context':path})
    def test_source_must_be_immutable(self):
        with self.assertRaises(ValueError):self.make({**self.item,'revision':'main'})
    def test_credentials_and_arbitrary_urls_rejected(self):
        for value in ['https://github.com/owner/source','token@owner/source','owner/source?token=secret']:
            with self.assertRaises(ValueError):self.make({**self.item,'repository':value})
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):plan(json.dumps({'version':1,'images':[self.item,self.item]}),'b'*40)
    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValueError):self.make({**self.item,'secret':'not-allowed'})
    def test_context_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp,patch('build_request.subprocess.check_output',return_value='a'*40):
            p=Path(temp);(p/'source').mkdir();(p/'outside').mkdir();(p/'source/image').symlink_to(p/'outside',target_is_directory=True)
            with self.assertRaises(ValueError):verify_source(self.item,p/'source')
    def test_source_hash_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp,patch('build_request.subprocess.check_output',return_value='a'*40):
            p=Path(temp);(p/'image').mkdir();(p/'image/Dockerfile').write_bytes(b'FROM scratch\n')
            self.assertEqual(verify_source(self.item,p)['file'],str(p/'image/Dockerfile'))
            (p/'image/Dockerfile').write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_source(self.item,p)

if __name__=='__main__':unittest.main()
