import hashlib,json,os,stat,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_request
from registry_receipt import verified_metadata

class ArtifactIdentityTests(unittest.TestCase):
 def test_context_contents_modes_links_and_ignore_are_bound(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'Dockerfile').write_text('FROM scratch\n');a=build_request.context_snapshot(p)
   (p/'.dockerignore').write_text('ignored\n');b=build_request.context_snapshot(p);self.assertNotEqual(a,b)
   (p/'ignored').write_bytes(b'also bound despite dockerignore');c=build_request.context_snapshot(p);self.assertNotEqual(b,c)
   (p/'Dockerfile').chmod(0o755);d=build_request.context_snapshot(p);self.assertNotEqual(c,d)
   (p/'inside').symlink_to('Dockerfile');e=build_request.context_snapshot(p);self.assertNotEqual(d,e)
   self.assertEqual(e,build_request.context_snapshot(p))
 def test_nested_escaping_links_are_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'data').mkdir();(p/'data/link').symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):build_request.context_snapshot(p)
 def test_special_context_files_are_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);os.mkfifo(p/'pipe')
   with self.assertRaises(ValueError):build_request.context_snapshot(p)
 def test_git_metadata_is_not_build_identity(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'Dockerfile').write_text('FROM scratch\n');a=build_request.context_snapshot(p)
   (p/'.git').mkdir();(p/'.git/HEAD').write_text('private checkout state')
   self.assertEqual(a,build_request.context_snapshot(p))
 def test_runtime_config_identity_required(self):
  image={'schemaVersion':2,'layers':[]}
  with self.assertRaises(ValueError):verified_metadata('registry.example.com/team/image','sha256:'+'a'*64,lambda *_:image)
 def test_index_manifest_and_config_are_distinct(self):
  a,b,c=['sha256:'+x*64 for x in 'abc'];image={'schemaVersion':2,'config':{'digest':c,'size':45},'layers':[]}
  index={'schemaVersion':2,'manifests':[{'digest':b,'platform':{'os':'linux','architecture':'amd64'}}]}
  r=verified_metadata('registry.example.com/team/image',a,lambda _,d:index if d==a else image)
  self.assertEqual((r['digest'],r['platform_digest'],r['config_digest']),(a,b,c))
 def test_malformed_config_is_rejected(self):
  for digest in ['latest','sha256:bad','']:
   with self.subTest(digest=digest),self.assertRaises(ValueError):
    verified_metadata('registry.example.com/team/image','sha256:'+'a'*64,lambda *_:{'schemaVersion':2,'config':{'digest':digest,'size':2},'layers':[]})
