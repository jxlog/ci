"""Mirror one public runtime manifest without rebuilding or changing its digest."""
import base64,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
from registry_target import target
from registry_receipt import decoded,verified_metadata

DIGEST=re.compile(r"sha256:[a-f0-9]{64}\Z")
def require(ok,message):
    if not ok:raise ValueError(message)

def source_parts(value):
    require(isinstance(value,str) and len(value)<=400 and not re.search(r"[\s\\]",value),'Invalid source reference')
    if '@' in value:
        base,suffix=value.rsplit('@',1);require(DIGEST.fullmatch(suffix),'Invalid source digest')
    else:
        require(value.rfind(':')>value.rfind('/'),'Explicit source tag or digest required')
        base,suffix=value.rsplit(':',1);require(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}',suffix),'Invalid source tag')
    target(base)
    return base

def request_plan(value,commit):
    require(isinstance(value,dict) and set(value)=={'version','source','platform'} and value['version']==1,'Unexpected mirror request fields')
    require(re.fullmatch(r'[a-f0-9]{40}',commit),'Pinned pipeline required')
    source_parts(value['source']);require(value['platform']=='linux/amd64','Unqualified mirror platform')
    key=hashlib.sha256((commit+'\n'+json.dumps(value,sort_keys=True,separators=(',',':'))).encode()).hexdigest()[:32]
    return {**value,'image_tag':'mirror-'+key}

def checked(command,timeout=130,runner=subprocess.run):
    try:r=runner(command,capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired:raise RuntimeError('Registry command timed out; reconcile the known request') from None
    if r.returncode:raise RuntimeError('Registry command failed; credential-bearing stderr withheld')
    require(len(r.stdout)<=4*1024*1024,'Registry response too large')
    return r.stdout

def inspect(reference,auth,flags):
    return checked(['skopeo','--command-timeout=90s','inspect','--authfile',auth,'--retry-times','2',*flags,'docker://'+reference])

def digest_at(reference,auth,absent_ok=False):
    command=['skopeo','--command-timeout=90s','inspect','--authfile',auth,'--retry-times','2','--no-tags','--format','{{.Digest}}','docker://'+reference]
    try:r=subprocess.run(command,capture_output=True,timeout=130)
    except subprocess.TimeoutExpired:raise RuntimeError('Registry digest observation timed out') from None
    if r.returncode:
        error=r.stderr.decode(errors='replace').lower()
        if absent_ok and any(x in error for x in ['manifest unknown','manifest_unknown','name unknown']):return None
        raise RuntimeError('Registry digest observation failed; absence not established')
    digest=r.stdout.decode().strip();require(DIGEST.fullmatch(digest),'Invalid observed digest');return digest

def guarded_copy(source_base,digest,destination,existing,source_auth,dest_auth,digestfile,runner=subprocess.run):
    require(DIGEST.fullmatch(digest),'Invalid immutable source digest')
    require(existing is None or existing==digest,'Destination tag already points at another image; never overwrite')
    if existing==digest:return False
    command=['skopeo','--command-timeout=18000s','copy','--preserve-digests','--retry-times','3','--src-authfile',source_auth,'--dest-authfile',dest_auth,'--digestfile',str(digestfile),'docker://'+source_base+'@'+digest,'docker://'+destination]
    try:r=runner(command,capture_output=True,timeout=18030)
    except subprocess.TimeoutExpired:raise RuntimeError('Copy outcome unconfirmed; inspect destination before another run') from None
    require(r.returncode==0,'Copy failed; no success receipt emitted')
    require(Path(digestfile).read_text().strip()==digest,'Copy did not preserve runtime digest')
    return True

def main():
    action=sys.argv[1]
    if action=='plan':
        ref=os.environ['GITHUB_REF'];commit=os.environ['GITHUB_SHA'];tag=os.environ['GITHUB_REF_NAME']
        require(ref=='refs/tags/'+tag and re.fullmatch(r'mirror-[a-z0-9-]{1,80}',tag),'Invalid mirror trigger')
        def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
        require(git('cat-file','-t',ref)=='tag' and git('rev-parse',ref+'^{commit}')==commit,'Annotated request identity differs')
        text=git('cat-file','-p',ref);require(len(text.encode())<=8192,'Mirror request too large')
        plan=request_plan(json.loads(text.split('\n\n',1)[1]),commit)
        Path('mirror-plan.json').write_text(json.dumps(plan,sort_keys=True)+'\n');print(json.dumps(plan));return
    if action=='auth':
        registry,_=target(os.environ['IMAGE']);username=os.environ['REGISTRY_USERNAME'];password=os.environ['REGISTRY_PASSWORD']
        require(username and password,'Missing configured registry credentials')
        os.umask(0o077)
        auth=base64.b64encode((username+':'+password).encode()).decode()
        Path(os.environ['MIRROR_DEST_AUTH']).write_text(json.dumps({'auths':{registry:{'auth':auth}}}))
        Path(os.environ['MIRROR_SOURCE_AUTH']).write_text('{"auths":{}}\n');return
    require(action=='copy','Unknown mirror action')
    plan=json.loads(Path('mirror-plan.json').read_text());source=plan['source'];source_base=source_parts(source)
    image=os.environ['IMAGE'];target(image);dest=image+':'+plan['image_tag'];sa=os.environ['MIRROR_SOURCE_AUTH'];da=os.environ['MIRROR_DEST_AUTH']
    source_digest=digest_at(source,sa)
    meta=verified_metadata(source_base,source_digest,read=lambda name,d:decoded(inspect(name+'@'+d,sa,['--raw']),d))
    runtime=meta['platform_digest']
    details=json.loads(inspect(source_base+'@'+runtime,sa,['--no-tags']))
    require(details.get('Os')=='linux' and details.get('Architecture')=='amd64','Runtime platform differs')
    print(json.dumps({'phase':'copying','source_digest':source_digest,'runtime_digest':runtime,'compressed_layer_bytes':meta['compressed_layer_bytes']}),flush=True)
    start=time.monotonic();copied=guarded_copy(source_base,runtime,dest,digest_at(dest,da,True),sa,da,Path('copied-digest.txt'))
    require(digest_at(dest,da)==runtime,'Destination tag digest differs')
    verified=verified_metadata(image,runtime,read=lambda name,d:decoded(inspect(name+'@'+d,da,['--raw']),d))
    require(verified['config_digest']==meta['config_digest'],'Destination config differs')
    run_id=int(os.environ['GITHUB_RUN_ID']);attempt=int(os.environ['GITHUB_RUN_ATTEMPT'])
    require(run_id>0 and attempt>0,'Invalid run identity')
    receipt={'schema_version':1,'kind':'registry_mirror','repository':os.environ['GITHUB_REPOSITORY'],'workflow_path':'.github/workflows/mirror-images.yml','pipeline_commit':os.environ['GITHUB_SHA'],'trigger_tag':os.environ['GITHUB_REF_NAME'],'run_id':run_id,'run_attempt':attempt,'request':plan,'image':image,'image_tag':plan['image_tag'],'source':source,'source_digest':source_digest,'source_platform_digest':runtime,'source_config_digest':meta['config_digest'],'preserved_runtime_digest':True,'copied_this_run':copied,'copy_and_verify_seconds':time.monotonic()-start,'runtime_test':'not_performed',**verified}
    name=f'receipt-{plan["image_tag"]}-{run_id}-{attempt}.json';Path(name).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('receipt='+name+'\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('### Digest-preserving runtime mirror\n```json\n'+json.dumps(receipt,indent=2)+'\n```\n')
    print('MIRROR_RECEIPT_JSON='+json.dumps(receipt,sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Mirror failed: '+str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Mirror failed: '+type(exc).__name__,file=sys.stderr);raise SystemExit(1)
