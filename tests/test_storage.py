"""Execute the storage JavaScript emitted by the pinned native hook in Node."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import polish


# Verbatim storage portion of EVO 9ee9a542's k_hook_js. Keep tests independent
# of downloaded archives and generated build trees; the patch checks its anchors.
UPSTREAM = r'''"var lastSnap='';"
"function snap(){var o={};try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i),v=localStorage.getItem(k);"
" if(v!==null&&v.length<=524288)o[k]=v;}}catch(e){}return JSON.stringify(o);}"
"try{if(!sessionStorage.getItem('__evoRestored')){var sx=new XMLHttpRequest();sx.open('GET','/evo/storage',false);sx.send(null);"
" if(sx.status===200){var so=JSON.parse(sx.responseText||'{}');localStorage.clear();"
"  for(var sk in so){if(Object.prototype.hasOwnProperty.call(so,sk))localStorage.setItem(sk,so[sk]);}"
"  sessionStorage.setItem('__evoRestored','1');}}}catch(e){}"
"lastSnap=snap();"
"function saveNow(kind){try{var sv=snap();if(sv===lastSnap)return;lastSnap=sv;"
" if(kind===2&&navigator.sendBeacon){navigator.sendBeacon('/evo/storage',sv);return;}"
" var x=new XMLHttpRequest();x.open('POST','/evo/storage',kind!==1);x.setRequestHeader('Content-Type','application/json');x.send(sv);}catch(e){}}"
"setInterval(function(){saveNow(0);},5000);"
"window.addEventListener('pagehide',function(){saveNow(2);});"
"document.addEventListener('visibilitychange',function(){if(document.hidden)saveNow(2);});"'''

HARNESS = r'''
const vm=require('vm'),assert=require('assert');
const seed={access_token:'synthetic-token',refresh_token:'synthetic-refresh',
 profiles:'[{"id":"synthetic-profile"}]',activeProfileId:'synthetic-profile'};
function boot(options={}) {
 let reads=0,readFailure=options.initialReadFailure||null,empty=false,subset=false,writeFailure=null;
 let data=new Map(Object.entries(options.initial||seed));
 const events={},posts=[],pending=[],beacons=[];
 let disk=JSON.stringify(options.saved||seed),mode='ok',tick;
 class Storage {
  constructor(session=false){this.session=session;this.values=new Map();}
  get length(){if(this.session)return this.values.size;
   if(readFailure==='length')throw Error('length unavailable');
   return empty?0:subset?1:data.size;}
  key(i){if(!this.session&&readFailure==='key'&&i===1)return null;
   return [...(this.session?this.values:data).keys()][i]??null;}
  getItem(k){if(!this.session && ++reads===readFailure)throw Error('read unavailable');
   if(!this.session&&readFailure==='null'&&reads===2)return null;
   return (this.session?this.values:data).get(String(k))??null;}
  setItem(k,v){if(writeFailure==='all'||writeFailure===String(k))throw Error('quota');
   (this.session?this.values:data).set(String(k),String(v));}
  removeItem(k){if(writeFailure==='remove')throw Error('read only');
   (this.session?this.values:data).delete(String(k));}
  clear(){if(writeFailure==='clear')throw Error('read only');
   (this.session?this.values:data).clear();}
 }
 const localStorage=new Storage(),sessionStorage=new Storage(true);
 if(options.restored)sessionStorage.setItem('__evoRestored','1');
 writeFailure=options.restoreFailure||null;
 class XHR {
  open(method,url,async){this.method=method;this.async=async;}
  setRequestHeader(){}
  send(body){
   if(this.method==='GET'){
    this.status=options.getStatus??200;
    this.responseText=options.response??disk;return;
   }
   posts.push(body);
   if(mode==='throw')throw Error('network');
   const finish=()=>{this.status=mode==='reject'?500:204;
    if(this.status===204)disk=body;
    if(this.onload)this.onload();if(this.onreadystatechange)this.onreadystatechange();};
   if(this.async)pending.push(finish);else finish();
  }
 }
 const context={Storage,localStorage,sessionStorage,XMLHttpRequest:XHR,
  navigator:{sendBeacon(url,body){beacons.push(body);if(mode==='throw')throw Error('network');
   if(mode==='reject')return false;pending.push(()=>{disk=body;});return true;}},
  setInterval(fn){tick=fn;},document:{hidden:false,addEventListener(k,fn){events[k]=fn;}},
  addEventListener(k,fn){events[k]=fn;}};
 context.window=context;
 if(options.trackingUnavailable)Object.freeze(Storage.prototype);
 vm.runInNewContext('(function(){'+process.argv[1]+'})();',context);
 writeFailure=null;reads=0;readFailure=null;
 return {localStorage,sessionStorage,posts,pending,beacons,
  tick(){tick();},hide(){events.pagehide();},hidden(){context.document.hidden=true;events.visibilitychange();},
  flush(reverse=false){while(pending.length)(reverse?pending.pop():pending.shift())();},
  failRead(value){reads=0;readFailure=value;},empty(value=true){empty=value;},subset(){subset=true;},
  failWrite(value){writeFailure=value;},mode(value){mode=value;},disk(){return JSON.parse(disk);},
  attempted(){return posts.concat(beacons).map(JSON.parse);}};
}
'''


class StorageTests(unittest.TestCase):
    def run_js(self, scenario):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        source = polish.patch_storage_hook(UPSTREAM)
        # Same concatenation performed by C, not a separately maintained JS fix.
        hook = ''.join(json.loads(line) for line in source.splitlines()
                       if line.startswith('"'))
        result = subprocess.run([node, '-e', HARNESS + scenario, hook],
                                timeout=10, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unchanged_and_changed_controls(self):
        self.run_js(r'''
const h=boot();h.tick();h.hide();h.hidden();assert.deepEqual(h.attempted(),[]);
h.localStorage.setItem('activeProfileId','next-profile');h.tick();h.flush();
assert.equal(h.disk().activeProfileId,'next-profile');
h.tick();h.hide();assert.equal(h.attempted().length,1);
''')

    def test_failed_reads_never_save_empty_or_partial_state(self):
        self.run_js(r'''
for(const failure of ['length',1,3,'key','null'])for(const trigger of ['tick','hide','hidden']){
 const h=boot();h.localStorage.setItem('activeProfileId','next-profile');
 h.failRead(failure);h[trigger]();h.flush();assert.deepEqual(h.attempted(),[]);
 assert.deepEqual(h.disk(),seed);
 h.failRead(null);h.tick();h.flush();assert.equal(h.disk().activeProfileId,'next-profile');
}
''')

    def test_unexpected_empty_or_partial_enumeration_is_not_a_reset(self):
        self.run_js(r'''
for(const trigger of ['tick','hide','hidden'])for(const subset of [false,true]){
 const h=boot();if(subset)h.subset();else h.empty();h[trigger]();h.flush();
 assert.deepEqual(h.attempted(),[]);assert.deepEqual(h.disk(),seed);
}
''')

    def test_explicit_logout_and_reset_are_persisted(self):
        self.run_js(r'''
const h=boot();
// SessionStore.clear plus accountLocalDataReset's removeItem contract.
for(const k of Object.keys(seed))h.localStorage.removeItem(k);
h.hide();h.flush();assert.deepEqual(h.attempted(),[{}]);assert.deepEqual(h.disk(),{});
const logout=boot({saved:{...seed,nuvio_web_installation_id:'keep-device-id'}});
for(const k of Object.keys(seed))logout.localStorage.removeItem(k);
logout.hidden();logout.flush();assert.deepEqual(logout.disk(),{nuvio_web_installation_id:'keep-device-id'});
const reset=boot();reset.localStorage.clear();reset.tick();reset.flush();
assert.deepEqual(reset.disk(),{});assert.deepEqual(reset.attempted(),[{}]);
const failed=boot();failed.failWrite('remove');
assert.throws(()=>failed.localStorage.removeItem('access_token'));
failed.empty();failed.hide();assert.deepEqual(failed.attempted(),[]);
''')

    def test_failed_transport_retries_identical_snapshot(self):
        self.run_js(r'''
for(const failure of ['throw','reject'])for(const trigger of ['tick','hide','hidden']){
 const h=boot();h.localStorage.setItem('activeProfileId','next-profile');
 h.mode(failure);h[trigger]();h.flush();assert.deepEqual(h.disk(),seed);
 h.mode('ok');h.tick();h.flush();assert.equal(h.disk().activeProfileId,'next-profile');
 assert.equal(h.attempted().length,2);h.tick();assert.equal(h.attempted().length,2);
}
''')

    def test_saves_cannot_arrive_out_of_order(self):
        self.run_js(r'''
for(const trigger of ['tick','hide','hidden']){
 const h=boot();h.localStorage.setItem('activeProfileId','older');h.tick();
 h.localStorage.setItem('activeProfileId','newer');h[trigger]();h.flush(true);h.tick();h.flush();
 assert.equal(h.disk().activeProfileId,'newer');
 h.tick();assert.equal(h.attempted().length,2);
}
''')

    def test_failed_restore_cannot_overwrite_disk(self):
        self.run_js(r'''
for(const options of [{restoreFailure:'clear'},{restoreFailure:'refresh_token'},
 {restoreFailure:'__evoRestored'},{getStatus:500},{response:'broken'},
 {response:'null'},{response:'[]'},{response:'{"access_token":42}'},{response:''}]){
 const h=boot(options);h.localStorage.setItem('activeProfileId','new-value');
 h.tick();h.hide();h.hidden();h.flush();assert.deepEqual(h.attempted(),[]);
 assert.deepEqual(h.disk(),seed);
}
''')

    def test_session_reload_and_storage_key_controls(self):
        self.run_js(r'''
const h=boot({restored:true});h.localStorage.setItem('__proto__','safe-value');
h.localStorage.setItem('cache','x'.repeat(524289));h.tick();h.flush();
assert.equal(h.disk()['__proto__'],'safe-value');assert.equal(h.disk().cache,undefined);
h.sessionStorage.clear();h.empty();h.hide();assert.equal(h.attempted().length,1);
const fresh=boot({initial:{},saved:{}});fresh.localStorage.setItem('profiles','[]');
fresh.tick();fresh.flush();assert.deepEqual(fresh.disk(),{profiles:'[]'});
''')

    def test_unavailable_startup_snapshot_or_tracking_preserves_disk(self):
        self.run_js(r'''
for(const options of [{restored:true,initialReadFailure:'length'},
 {restored:true,initialReadFailure:3},{trackingUnavailable:true}]){
 const h=boot(options);h.localStorage.setItem('activeProfileId','new-value');
 h.tick();h.hide();h.flush();assert.deepEqual(h.attempted(),[]);assert.deepEqual(h.disk(),seed);
}
''')


if __name__ == '__main__':
    unittest.main()
