import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mirror_image import source_parts,request_plan,guarded_copy,checked
D='sha256:'+'a'*64
class MirrorTests(unittest.TestCase):
    def test_source_requires_explicit_tag_and_rejects_transport_credentials_and_shell(self):
        self.assertEqual(source_parts('docker.io/library/alpine:3.21'),'docker.io/library/alpine')
        self.assertEqual(source_parts('ghcr.io/owner/image@'+D),'ghcr.io/owner/image')
        for value in ['docker.io/library/alpine','https://docker.io/library/alpine:3','user:pass@docker.io/team/image:1','docker.io/team/image:1\nflag','docker.io/team/image:1;echo','--creds=x']:
            with self.subTest(value=value),self.assertRaises(ValueError):source_parts(value)
    def test_request_rejects_destination_override_private_inputs_and_wrong_platform(self):
        value={'version':1,'source':'docker.io/library/alpine:3.21','platform':'linux/amd64'}
        for change in [{'image':'other.example/team/image'},{'password':'x'},{'platform':'linux/arm64'}]:
            with self.assertRaises(ValueError):request_plan({**value,**change},'a'*40)
    def test_immutable_request_key_binds_source_and_pipeline(self):
        a={'version':1,'source':'docker.io/library/alpine:3.21','platform':'linux/amd64'}
        self.assertEqual(request_plan(a,'a'*40),request_plan(json.loads(json.dumps(a)),'a'*40))
        self.assertNotEqual(request_plan(a,'a'*40)['image_tag'],request_plan(a,'b'*40)['image_tag'])
        self.assertNotEqual(request_plan(a,'a'*40)['image_tag'],request_plan({**a,'source':'docker.io/library/alpine:3.20'},'a'*40)['image_tag'])
    def test_copy_pins_source_digest_and_preserves_destination_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'digest';calls=[]
            def runner(command,**kwargs):
                calls.append(command);p.write_text(D+'\n');return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
            self.assertTrue(guarded_copy('docker.io/library/alpine',D,'registry.example/team/image:mirror-x',None,'empty-auth','private-auth',p,runner))
            self.assertIn('--preserve-digests',calls[0]);self.assertIn('docker://docker.io/library/alpine@'+D,calls[0]);self.assertNotIn('docker',calls[0]);self.assertEqual(len(calls),1)
    def test_existing_other_digest_never_overwritten_and_exact_digest_reused(self):
        def unexpected(*a,**k):raise AssertionError('Copy must not be invoked')
        with self.assertRaises(ValueError):guarded_copy('docker.io/library/alpine',D,'dest','sha256:'+'b'*64,'src','dst',Path('unused'),unexpected)
        self.assertFalse(guarded_copy('docker.io/library/alpine',D,'dest',D,'src','dst',Path('unused'),unexpected))
    def test_unpreserved_digest_or_failed_copy_cannot_emit_success(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'digest';p.write_text('sha256:'+'b'*64)
            for code in [0,1]:
                with self.assertRaises(ValueError):guarded_copy('docker.io/library/alpine',D,'dest',None,'src','dst',p,lambda *a,**k:SimpleNamespace(returncode=code,stdout=b'',stderr=b'private'))
    def test_error_does_not_expose_registry_capabilities_and_timeout_not_replayed(self):
        with self.assertRaisesRegex(RuntimeError,'withheld') as caught:checked(['fake'],runner=lambda *a,**k:SimpleNamespace(returncode=1,stdout=b'',stderr=b'password=secret'))
        self.assertNotIn('secret',str(caught.exception))
        calls=[]
        def timed(*a,**k):calls.append(1);raise subprocess.TimeoutExpired('copy',10)
        with self.assertRaises(RuntimeError):guarded_copy('docker.io/library/alpine',D,'dest',None,'src','dst',Path('unused'),timed)
        self.assertEqual(len(calls),1)
    def test_runner_context_is_not_used_before_assignment(self):
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/mirror-images.yml').read_text()
        job_env=workflow.split('    env:\n',1)[1].split('    steps:',1)[0]
        self.assertNotIn('${{ runner.',job_env)
        self.assertIn('          MIRROR_SOURCE_AUTH: ${{ runner.temp }}',workflow)
if __name__=='__main__':unittest.main()
