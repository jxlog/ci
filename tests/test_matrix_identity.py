import json,sys,unittest
from pathlib import Path
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_request import plan
class MatrixIdentityTests(unittest.TestCase):
 def test_matrix_job_name_contains_immutable_entry_identity(self):
  d=yaml.safe_load((Path(__file__).resolve().parents[1]/'.github/workflows/build-contexts.yml').read_text());self.assertIn('${{ matrix.key }}',d['jobs']['build']['name'])
 def test_same_context_on_different_sources_has_distinct_identity(self):
  base={'repository':'owner/source','revision':'a'*40,'context':'image','dockerfile':'Dockerfile','dockerfile_sha256':'b'*64};r=plan(json.dumps({'version':1,'images':[base,{**base,'revision':'c'*40}]}),'d'*40)['include'];self.assertNotEqual(r[0]['key'],r[1]['key'])
