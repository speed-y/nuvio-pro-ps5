"""Browser candidate discovery and the actual native candidate cache, offline."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

from tests.test_native_subtitles import compile_run, source_file
from scripts import subtitle_handoff

ROOT = Path(__file__).resolve().parents[1]


def frontend_file(relative):
    pin = next(p for p in json.loads((ROOT / 'deps.lock').read_text())['artifacts']
               if p['id'] == 'nuvio-tv-source')
    archive = Path(os.environ.get('NUVIO_CACHE_DIR', ROOT / '.cache')) / pin['cache_file']
    if not archive.exists():
        raise unittest.SkipTest('Pinned Nuvio archive not cached; no network fetch')
    with archive.open('rb') as handle:
        if hashlib.file_digest(handle, 'sha256').hexdigest() != pin['sha256']:
            raise RuntimeError('Cached Nuvio archive checksum mismatch')
    with tarfile.open(archive) as handle:
        return handle.extractfile(pin['directory'] + '/' + relative).read().decode()


class SubtitleHandoffTests(unittest.TestCase):
    def test_real_repository_publishes_before_slow_addon_or_candidate_id(self):
        loader = subtitle_handoff.patch_loader_source(frontend_file(
            'js/ui/screens/player/playerScreenMethods-68-load-subtitles.js'))
        original_repository = frontend_file('js/data/repository/subtitleRepository.js')
        repository = subtitle_handoff.patch_repository_source(original_repository)
        merge = frontend_file('js/ui/screens/player/playerScreenMethods-12-normalize-embedded-audio-tracks.js')
        harness = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const input=JSON.parse(fs.readFileSync(process.argv[1],'utf8')),scenario=process.argv[3];
 const evaluate=(ctx,source)=>vm.runInContext(source.replace(/^import .*;$/gm,'').replace(/export /g,''),ctx);
 const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
 const fast={url:'https://subs.invalid/fast.srt',lang:'en'};
 const foreign={url:'https://subs.invalid/foreign.srt',lang:'fr'};
 async function setup({ps5=true,preferred=false,canonical=false,original=false}={}){
  let profile='one',sent,settings={addonSubtitleStartupMode:preferred===true?'PREFERRED_ONLY':'ALL_SUBTITLES',
   subtitleStyle:{showOnlyPreferredLanguages:preferred==='style'}};
  const timers=new Map(),requests=[];let timerId=0;
  const params={itemId:canonical?'custom:123':scenario==='ids'?'tt123:alternate':'tt123',itemType:'movie'};
  const candidate={id:'source-one'};
  const screen={params,playerMountToken:1,activePlaybackUrl:'https://media.invalid/film',streamCandidates:[],
   getCurrentStreamCandidate:()=>candidate,refreshTrackDialogs(){},getStartupPreferredSubtitleLanguageTargets:()=>['en'],
   buildSubtitleLookupContext:()=>({id:params.itemId,type:'movie',title:'Fixture',year:'2020'})};
  const router={current:'player',currentParams:params,getCurrentScreen:()=>screen};
  const addon=host=>({baseUrl:`https://${host}.invalid`,displayName:host,resources:[{name:'subtitles',types:['movie']}]});
  const canonicalAddons=[
   {...addon('fast'),resources:[{name:'subtitles',types:['movie'],idPrefixes:['tt']}]},
   {...addon('wrong-type'),resources:[{name:'subtitles',types:['series'],idPrefixes:['tt']}]},
   {...addon('wrong-resource-prefix'),resources:[{name:'subtitles',types:['movie'],idPrefixes:['other:']}]},
   {...addon('wrong-addon-prefix'),idPrefixes:['other:']}];
  const ctx=vm.createContext({URL,AbortController,__NUVIO_PS5__:ps5,screen,console,
   Router:router,ProfileManager:{getActiveProfileId:()=>profile},
   setTimeout(fn,ms){timers.set(++timerId,{fn,ms});return timerId;},clearTimeout(id){timers.delete(id);},
   addonRepository:{getInstalledAddons:async()=>canonical?canonicalAddons:
     scenario==='ids'?[addon('fast')]:[addon('fast'),addon('slow')],canonicalizeUrl:s=>s},
   catalogRepository:{getCatalog:async()=>{
    assert(canonical,'Unexpected canonical lookup');
    return {status:'success',data:{items:[{id:'tt123',type:'movie',name:'Fixture',year:'2020'}]}};}},
   safeApiCall:async fn=>({status:'success',data:await fn()}),
   SubtitleApi:{getSubtitles:url=>new Promise(resolve=>requests.push({url,resolve}))},
   async fetch(url,options){assert.equal(url,'/evo/subtitles');sent=JSON.parse(options.body);return {ok:true};}});
  evaluate(ctx,original?input.originalRepository:input.repository);vm.runInContext('globalThis.repo=subtitleRepository;',ctx);
  ctx.internals={subtitleRepository:ctx.repo,PlayerSettingsStore:{get:()=>settings},
   normalizeSubtitleLanguageKey:s=>String(s).toLowerCase()};
  evaluate(ctx,input.merge);evaluate(ctx,input.loader);
  vm.runInContext('Object.assign(screen,createPlayerScreenMethods12(),createPlayerScreenMethods68());',ctx);
  vm.runInContext(input.general+input.sender,ctx);
  return {ctx,screen,router,candidate,requests,timers,flush,profile:value=>{profile=value;},sent:()=>sent};
 }
 // Exercise the actual repository, loader, merger and sender through the same
 // four-second deadline; one successful request must not wait for another.
 for(const preferred of [false,true,'style']){
  const f=await setup({preferred});const preparing=f.ctx.__nuvioPrepareSubtitles();await flush();
  assert.equal(f.requests.length,scenario==='ids'?1:2);
  f.requests[0].resolve({subtitles:[fast,foreign,fast]});await flush();
  assert.equal(f.requests.length,2); // second addon OR next candidate ID remains pending
  for(const timer of [...f.timers.values()])if(timer.ms===4000)timer.fn();
  assert.equal(await preparing,true);assert.equal(await f.ctx.__nuvioSendSubtitles('one'),true);
  assert.equal(f.sent().subtitles.length,preferred?1:2,'fast repository result missing at handoff deadline');
  assert.equal(f.sent().subtitles[0].url,fast.url);
  const frozen=JSON.stringify(f.sent());
  f.requests[1].resolve({subtitles:[fast,foreign]});await flush();
  assert.equal(f.screen.subtitles.length,preferred?1:2); // actual final dedup and filter
  assert.equal(JSON.stringify(f.sent()),frozen); // late arrival cannot mutate sent DTO
 }
 // Every stale-context boundary rejects partial AND final publications.
 for(const change of ['mount','token','profile','source','sourceId','route','routeParams','screen','params','identity']){
  const f=await setup();const loading=f.screen.loadSubtitles();await flush();
  if(change==='mount')f.screen.playerMountToken++;
  if(change==='token')f.screen.subtitleLoadToken++;
  if(change==='profile')f.profile('two');
  if(change==='source')f.screen.activePlaybackUrl+='-other';
  if(change==='sourceId')f.candidate.id='source-two';
  if(change==='route')f.router.current='home';
  if(change==='routeParams')f.router.currentParams={...f.router.currentParams};
  if(change==='screen')f.router.getCurrentScreen=()=>({});
  if(change==='params')f.screen.params={...f.screen.params};
  if(change==='identity')f.screen.params.contentId='another-title';
  f.requests[0].resolve({subtitles:[fast]});await flush();assert.equal(f.screen.subtitles.length,0,change+' partial');
  f.requests[1].resolve({subtitles:[foreign]});await loading;
  assert.equal(f.screen.subtitles.length,0,change+' final');
 }
 // A new profile or source identity must not reuse the guarded-out promise.
 for(const change of ['profile','sourceId']){
  const f=await setup();const old=f.screen.loadSubtitles();await flush();
  if(change==='profile')f.profile('two');else f.candidate.id='source-two';
  const fresh=f.screen.loadSubtitles();assert.notEqual(old,fresh);await flush();
  for(let i=0;i<f.requests.length;i++){f.requests[i].resolve({subtitles:[fast]});await flush();}
  await Promise.all([old,fresh]);assert.equal(f.screen.subtitles.length,1);
 }
 // Non-PS5 callers retain the original all-results-at-once behavior.
 const f=await setup({ps5:false});const loading=f.screen.loadSubtitles();await flush();
 f.requests[0].resolve({subtitles:[fast]});await flush();assert.equal(f.screen.subtitles.length,0);
 f.requests[1].resolve({subtitles:[foreign]});await loading;assert.equal(f.screen.subtitles.length,2);
 // Canonical tt lookup: original excludes the valid resource, PS5 adaptation
 // accepts it without admitting incompatible resource types or either prefix.
 for(const [original,ps5,expected] of [[true,true,0],[false,true,1],[false,false,0]]){
  const f=await setup({canonical:true,original,ps5});const loading=f.screen.loadSubtitles();await flush();
  assert.equal(f.requests.length,expected,'canonical resource eligibility');
  if(expected){
   assert(f.requests[0].url.includes('/tt123.json'));
   for(let i=0;i<f.requests.length;i++){
    assert(f.requests[i].url.startsWith('https://fast.invalid/'),'incompatible addon requested');
    f.requests[i].resolve({subtitles:[fast]});await flush();
   }
  }
  await loading;assert.equal(f.screen.subtitles.length,expected);
 }
 console.log('Actual repository '+scenario+': fast chunks survive deadline; canonical eligibility before=0 after=1; language/stale/non-PS5 controls passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'repository.json'
            fixture.write_text(json.dumps({'repository': repository, 'originalRepository': original_repository,
                'loader': loader, 'merge': merge,
                'general': (ROOT / 'scripts/ps5-general.js').read_text().split('// Preference identities')[0],
                'sender': (ROOT / 'scripts/ps5-subtitles.js').read_text()}))
            for scenario in ('addons', 'ids'):
                with self.subTest(scenario=scenario):
                    subprocess.run(['node', '-e', harness, str(fixture), str(ROOT), scenario], check=True, timeout=15)

    def test_real_initial_mount_and_loader_share_discovery(self):
        loader = frontend_file('js/ui/screens/player/playerScreenMethods-68-load-subtitles.js')
        mount = frontend_file('js/ui/screens/player/playerScreenMethods-01-mount.js')
        mount_epoch = mount.split('      const mountToken = ', 1)[1].split('\n', 2)[:2]
        mount_epoch = 'const mountToken = ' + '\n'.join(mount_epoch)
        initialization = frontend_file('js/ui/screens/player/playerMountStateInitialization.js')
        reset = next(line for line in initialization.splitlines() if 'this.subtitleLoadToken = ' in line)
        # Execute the real direct-stream startup ordering, ending at discovery.
        mount = mount[mount.index('      if (initialStreamUrl && !this.isExternalFrameMode()) {'):]
        mount = mount.split('        this.syncTrackState();', 1)[0] + '\n      }\n'
        harness = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const data=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
 const results=[];
 for(const [adapted,source] of data.loaders.entries()) {
   const pending=[];let preparing,sent;
   const params={itemId:'tt1234567',itemType:'movie'},candidate={id:'stream-one'};
   const screen={params,subtitles:[],refreshTrackDialogs(){},
     collectStreamSidecarSubtitles:()=>[],buildSubtitleLookupContext:()=>({type:'movie',id:'tt1234567'}),
     mergeSubtitleCandidates:(a,b)=>[...a,...b],isExternalFrameMode:()=>false,
     getStreamCandidateByUrl:()=>candidate,getCurrentStreamCandidate:()=>candidate,
     getEngineFsStateForStream:()=>null,isCurrentSourceLikelyHls:()=>false,
     enableStartupAudioGate(){},buildPlaybackContext:()=>({}),
     loadManifestTrackDataForCurrentStream(){},startTrackDiscoveryWindow(){},schedulePlaybackStallGuard(){}};
   const ctx=vm.createContext({URL,AbortController,setTimeout,clearTimeout,__NUVIO_PS5__:true,
     Router:{current:'player',currentParams:params,getCurrentScreen:()=>screen},
     ProfileManager:{getActiveProfileId:()=> 'one'},
     async fetch(url,options){assert.equal(url,'/evo/subtitles');sent=JSON.parse(options.body);return {ok:true};},
     internals:{subtitleRepository:{getSubtitles:()=>new Promise(resolve=>pending.push(resolve))},
       PlayerSettingsStore:{get:()=>({addonSubtitleStartupMode:'ALL_SUBTITLES'})}},
     Environment:{isWebOS:()=>false},shouldAllowNativePlaybackDuringStartupAudioGate:()=>false,
     initialStreamUrl:'https://media.invalid/film',mountToken:1,screen});
   const general=fs.readFileSync(process.argv[2]+'/scripts/ps5-general.js','utf8').split('// Preference identities')[0];
   vm.runInContext(general+fs.readFileSync(process.argv[2]+'/scripts/ps5-subtitles.js','utf8'),ctx);
   vm.runInContext(source.replace(/^import .*;$/gm,'').replace('export function','function')+
     '\nObject.assign(screen,createPlayerScreenMethods68());',ctx);
   screen.startPlayerControllerPlayback=()=>{preparing=ctx.__nuvioPrepareSubtitles();return Promise.resolve();};
   await vm.runInContext('(async function(){'+data.mount+'}).call(screen)',ctx);
   assert.equal(pending.length,adapted?1:2);
   pending[0]([{url:'https://subs.invalid/current.vtt?token=fixture',lang:'en',addonName:'Example'}]);
   assert.equal(await preparing,true);
   assert.equal(await ctx.__nuvioSendSubtitles('session-one'),true);
   results.push(sent.subtitles.length);
   if(!adapted) {pending[1]([]);await Promise.resolve();await Promise.resolve();}
   else {
     // Settled lookups can refresh; a different route/source cannot reuse an old request.
     const refresh=screen.loadSubtitles();assert.equal(pending.length,2);
     const same=screen.loadSubtitles();assert.equal(same,refresh);
     screen.activePlaybackUrl='https://media.invalid/other';
     const changed=screen.loadSubtitles();assert.equal(pending.length,3);
     pending[1]([{url:'https://subs.invalid/stale.srt'}]);await refresh;
     assert.equal(screen.subtitles.length,0);
     pending[2]([{url:'https://subs.invalid/new.srt'}]);await changed;
     assert.equal(screen.subtitles[0].url,'https://subs.invalid/new.srt');
   }
   // Actual remount resets the ordinary token. Before adaptation both
   // requests become token 1, so the old mount can overwrite the new list.
   const base=pending.length;
   vm.runInContext('(function(){'+data.remount+'}).call(screen)',ctx);
   const oldMount=screen.loadSubtitles();
   vm.runInContext('(function(){'+data.remount+'}).call(screen)',ctx);
   const newMount=screen.loadSubtitles();assert.notEqual(oldMount,newMount);
   pending[base]([{url:'https://subs.invalid/old-mount.srt'}]);await oldMount;
   assert.equal(screen.subtitles.length,adapted?0:1);
   pending[base+1]([{url:'https://subs.invalid/new-mount.srt'}]);await newMount;
   assert.equal(screen.subtitles[0].url,'https://subs.invalid/new-mount.srt');
   assert.equal(await ctx.__nuvioSendSubtitles('session-one'),false);
 }
 assert.deepEqual(results,[0,1]);
 console.log('Actual initial mount: candidates before=0 after=1; shared lookup and source-change controls passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'source.json'
            fixture.write_text(json.dumps({'mount': mount, 'remount': mount_epoch + '\n' + reset,
                'loaders': [loader, subtitle_handoff.patch_loader_source(loader)]}))
            subprocess.run(['node', '-e', harness, str(fixture), str(ROOT)], check=True, timeout=15)

    def test_embedded_choice_survives_remembered_online_restore(self):
        source = subtitle_handoff.patch_controller_source(
            source_file('core/src/services/PlaybackController.cpp'))
        # Execute the real restoration gates. The downstream automatic provider
        # lookup is deliberately outside this browser/manual-selection contract.
        restore = source.split('void PlaybackController::applyOnlineSubtitles()\n{', 1)[1]
        restore = restore.split('    if (prospero_subtitle_count > 0)', 1)[0]
        harness = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
static struct { std::string item_id="web:one",subtitleUrl,provider="web";
 bool isProvider()const{return true;} } m_source;
static int play_fmt=1,prospero_subtitle_requested_stream=-1,loads,active=0;
static char prospero_subtitle_external_label[96];
static bool isLiveSource(){return false;}
static void evo_osubs_key(char *s,size_t n){std::snprintf(s,n,"web:one");}
static int evo_osubs_active(){return active;}
static int evo_osubs_remembered(char *p,int,char *l,int){strcpy(p,"fixture");strcpy(l,"Online");return 1;}
static int prospero_subtitle_load_file_quiet(const char*){++loads;return 1;}
static void restore(){
''' + restore + r'''
}
int main(){
 restore();assert(loads==1 && !strcmp(prospero_subtitle_external_label,"Online"));
 loads=0;prospero_subtitle_requested_stream=3;restore();assert(!loads);
 prospero_subtitle_requested_stream=-1;active=-1;restore();assert(!loads);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            compile_run(harness, tmp, cpp=True)

    def test_delayed_candidates_limits_and_stale_browser_context(self):
        harness = r'''
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
(async()=>{
 let profile='one', sent;
 const timers=new Map(); let nextTimer=0;
 let finish;
 const screen={activePlaybackUrl:'https://media.invalid/film',ps5SubtitleLoadUrl:'https://media.invalid/film',
   getCurrentStreamCandidate:()=>({id:'stream-one'}), subtitles:[],
   ps5SubtitleLoadPromise:new Promise(resolve=>{finish=resolve;})};
 const Router={current:'player', currentParams:{videoId:'episode-one'},getCurrentScreen:()=>screen};
 const ctx=vm.createContext({URL,AbortController,Router,__NUVIO_PS5__:true,
   ProfileManager:{getActiveProfileId:()=>profile},
   setTimeout(fn,ms){timers.set(++nextTimer,{fn,ms});return nextTimer;},
   clearTimeout(id){timers.delete(id);},
   async fetch(url,options){assert.equal(url,'/evo/subtitles');sent=JSON.parse(options.body);return {ok:true};}});
 const general=fs.readFileSync(process.argv[1]+'/scripts/ps5-general.js','utf8').split('// Preference identities')[0];
 vm.runInContext(general+fs.readFileSync(process.argv[1]+'/scripts/ps5-subtitles.js','utf8'),ctx);
 const preparing=ctx.__nuvioPrepareSubtitles();
 screen.subtitles=[{url:'https://subs.invalid/one.vtt?token=fixture',lang:'en',addonName:'Example'},
   {url:'https://subs.invalid/one.vtt?token=fixture',lang:'en'},
   {url:'https://subs.invalid/auth.srt',headers:{Authorization:'fixture-only'}},
   {url:'file:///private/sub.srt'}, {url:'https://user:password@subs.invalid/sub.srt'}];
 finish(); assert.equal(await preparing,true);
 assert.equal(await ctx.__nuvioSendSubtitles('session-one'),true);
 assert.equal(sent.session,'session-one');assert.equal(sent.subtitles.length,1);
 assert.equal(sent.subtitles[0].url,'https://subs.invalid/one.vtt?token=fixture');
 assert.equal(sent.subtitles[0].lang,'en');assert.equal(sent.subtitles[0].source,'Example');
 profile='two';assert.equal(await ctx.__nuvioSendSubtitles('session-one'),false);
 profile='one';screen.activePlaybackUrl='https://media.invalid/different';
 assert.equal(await ctx.__nuvioSendSubtitles('session-one'),false);
 screen.ps5SubtitleLoadUrl=screen.activePlaybackUrl;
 screen.subtitles=Array.from({length:40},(_,i)=>({url:`https://subs.invalid/${i}.srt`,lang:'fr'}));
 screen.ps5SubtitleLoadPromise=Promise.resolve();await ctx.__nuvioPrepareSubtitles();
 assert.equal(await ctx.__nuvioSendSubtitles('session-two'),true);assert.equal(sent.subtitles.length,32);
 screen.ps5SubtitleLoadPromise=new Promise(resolve=>{finish=resolve;});
 const stale=ctx.__nuvioPrepareSubtitles();Router.currentParams={videoId:'episode-two'};
 finish();assert.equal(await stale,null);
 // A stalled addon cannot indefinitely hold playback; retain available sidecars.
 screen.ps5SubtitleLoadPromise=new Promise(()=>{});
 screen.subtitles=[{url:'https://subs.invalid/sidecar.srt',lang:'es'}];
 const bounded=ctx.__nuvioPrepareSubtitles();
 for(const timer of [...timers.values()])if(timer.ms===4000)timer.fn();
 assert.equal(await bounded,true);assert.equal(await ctx.__nuvioSendSubtitles('session-three'),true);
 assert.equal(sent.subtitles[0].lang,'es');assert.equal(timers.size,0);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        subprocess.run(['node', '-e', harness, str(ROOT)], check=True, timeout=15)

    def test_native_candidates_are_session_bound_and_stale_downloads_are_discarded(self):
        compiler = shutil.which('cc')
        cpp = shutil.which('c++')
        if not compiler or not cpp:
            self.skipTest('Host C/C++ compilers required')
        subtitle = source_file('media/src/evo_subtitle.c')
        clear = 'void prospero_subtitle_clear(void) {' + subtitle.split(
            'void prospero_subtitle_clear(void) {', 1)[1].split('void prospero_subtitle_trim(', 1)[0]
        interface = source_file('core/include/evo/interfaces/IPlaybackController.hpp')
        identity = 'struct PlaybackSource {' + interface.split('struct PlaybackSource {', 1)[1].split('\n};', 1)[0] + '\n};'
        picker = source_file('core/src/screens/SubtitlePickerScreen.cpp')
        gate = '    bool onlineForThis = false;' + picker.split(
            '    bool onlineForThis = false;', 1)[1].split('    if (onlineForThis) {', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for relative in ('addons/include/cJSON.h', 'addons/src/cJSON.c',
                             'addons/include/evo_online_subs.h', 'addons/include/evo_net.h',
                             'include/evo_data_path.h', 'media/include/evo_langpref.h',
                             'media/include/evo_langname.h'):
                (directory / Path(relative).name).write_text(source_file(relative))
            (directory / 'online.c').write_text(subtitle_handoff.patch_online_source(
                source_file('addons/src/evo_online_subs.c')))
            source = r'''
#define _DEFAULT_SOURCE
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include "cJSON.h"
#include "online.c"
void check_picker(const char *key);
static int prospero_subtitle_count,prospero_subtitle_delay_ms,prospero_secondary_delay_ms;
static double prospero_subtitle_time_scale;
static char prospero_subtitle_path[512],prospero_subtitle_external_label[96];
static void evo_subsync_cancel(void) {}
''' + clear + r'''
static pthread_mutex_t s_mx=PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t net_mx=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t net_cv=PTHREAD_COND_INITIALIZER;
static int entered,release_net;
static int header_value(const char *b,size_t n,const char *k,char *o,size_t c) {
 (void)b;(void)n;(void)k;snprintf(o,c,"%s","2");return 1;
}
static long parse_long(const char *s){return strtol(s,NULL,10);}
static void respond(int f,const char *s,const char *t,const char *b,size_t n) {
 (void)f;(void)s;(void)t;(void)b;(void)n;
}
int evo_lang_normalize(const char *s,char out[4]){(void)s;strcpy(out,"eng");return 1;}
int evo_langpref_rank(const char *s,char kind){(void)s;(void)kind;return 2;}
const char *evo_language_native_name(const char *s){return s;}
const char *evo_data_path(const char *name){return name;}
int evo_net_http_get_sync(const char *url,const char **h,int hn,char **out,size_t *n,int *status){
 (void)url;(void)h;(void)hn;pthread_mutex_lock(&net_mx);entered=1;pthread_cond_broadcast(&net_cv);
 while(!release_net) pthread_cond_wait(&net_cv,&net_mx);
 pthread_mutex_unlock(&net_mx);
 *out=strdup("1\n00:00:01,000 --> 00:00:02,000\nHello\n\n");*n=strlen(*out);*status=200;return 0;
}
''' + (ROOT / 'scripts/ps5-subtitles.c').read_text() + r'''
int main(void){
 const char *dto="{\"session\":\"one\",\"subtitles\":[{\"url\":\"https://subs.invalid/one.srt\",\"lang\":\"en\",\"source\":\"Example\"}]}";
 assert(subtitles_decode(dto,strlen(dto)));subtitles_handoff("wrong");s_play_subtitles=s_h_subtitles;
 char key[80];evo_webui_import_subtitles(key,sizeof key);assert(evo_osubs_count()==0);
 assert(subtitles_decode(dto,strlen(dto)));subtitles_handoff("one");s_play_subtitles=s_h_subtitles;
 evo_webui_import_subtitles(key,sizeof key);assert(!strcmp(key,"web:one"));assert(evo_osubs_count()==1);
 // The real clear routine runs during stopPlayback and again in subtitle setup.
 // It clears loaded external cues, NOT the separate online candidate cache.
 prospero_subtitle_clear();prospero_subtitle_clear();
 char cached_key[512];evo_osubs_key(cached_key,sizeof cached_key);
 assert(!strcmp(cached_key,key) && evo_osubs_count()==1);
 check_picker(key);
 evo_osub_t entry;assert(evo_osubs_get(0,&entry));assert(!strcmp(entry.url,"https://subs.invalid/one.srt"));
 assert(!strcmp(entry.source,"Example"));
 assert(evo_osubs_fetch_async(0)==0);
 pthread_mutex_lock(&net_mx);while(!entered)pthread_cond_wait(&net_cv,&net_mx);pthread_mutex_unlock(&net_mx);
 // A new video invalidates the completion, not just its visible label.
 evo_osubs_begin("web:two");pthread_mutex_lock(&net_mx);release_net=1;
 pthread_cond_broadcast(&net_cv);pthread_mutex_unlock(&net_mx);
 while(evo_osubs_fetching())usleep(1000);
 int index=-1,failed=0;assert(!evo_osubs_take_ready(&index,&failed));assert(!failed);
 evo_osubs_add("web:two","https://subs.invalid/two.srt","es","Second");
 assert(evo_osubs_fetch_async(0)==0);while(evo_osubs_fetching())usleep(1000);
 assert(evo_osubs_take_ready(&index,&failed));assert(index==0 && !failed);
 assert(evo_osubs_fetch_async(0)==0);evo_osubs_cancel_fetch();
 while(evo_osubs_fetching())usleep(1000);
 assert(!evo_osubs_take_ready(&index,&failed));assert(!failed);
 char body[]="{}";serve_subtitles(-1,"GET",body,2,0);
 assert(!subtitles_decode("{}",2));
}
'''
            path = directory / 'probe.c'
            path.write_text(source)
            picker_path = directory / 'picker.cpp'
            picker_path.write_text('''
#include <cassert>
#include <string>
#include "evo_online_subs.h"
''' + identity + '''
struct Controller {
 PlaybackSource source;
 const PlaybackSource& getSource() const {return source;}
} controller;
struct Application {
 static Application& getInstance(){static Application app;return app;}
 Controller* getPlaybackController(){return &controller;}
};
static bool online_for_this() {
''' + gate + '''
 return onlineForThis;
}
extern "C" void check_picker(const char *key) {
 controller.source.provider="web";controller.source.item_id=key;
 assert(online_for_this() && evo_osubs_count()==1);
 controller.source.item_id="web:another-session";assert(!online_for_this());
 controller.source.item_id=key;controller.source.provider.clear();assert(!online_for_this());
}
''')
            picker_object = directory / 'picker.o'
            subprocess.run([cpp, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                            '-I', tmp, '-c', str(picker_path), '-o', str(picker_object)],
                           check=True, timeout=30)
            binary = directory / 'probe'
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', '-I', tmp, str(path),
                            str(directory / 'cJSON.c'), str(picker_object),
                            '-lstdc++', '-lpthread', '-lm', '-o', str(binary)],
                           check=True, timeout=30)
            subprocess.run([str(binary)], cwd=tmp, check=True, timeout=15)

    def test_local_file_choice_owns_reopen_and_cancels_pending_online(self):
        from scripts import native_preferences, native_subtitles
        from tests.test_native_preferences import NATIVE_PRELUDE

        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'libavformat', 'libavcodec', 'libavutil'],
                               capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('FFmpeg development libraries unavailable')
        local = source_file('core/src/screens/SubtitleFileScreen.cpp')
        local = subtitle_handoff.patch_local_file_source(local)
        self.assertIn('#include "evo_online_subs.h"', local)
        with self.assertRaises(RuntimeError):
            subtitle_handoff.patch_local_file_source(local)
        activate = 'void SubtitleFileScreen::activate() {' + local.split(
            'void SubtitleFileScreen::activate() {', 1)[1].split(
            '\nvoid SubtitleFileScreen::navigate(', 1)[0]
        subtitle = native_preferences.patch_subtitle_source(native_subtitles.patch_subtitle_source(
            source_file('media/src/evo_subtitle.c')))
        # The actual cache/downloader and parser run here. Only network delivery
        # and screen-manager effects are controlled by the host fixture.
        prelude = NATIVE_PRELUDE.split('int evo_net_http_get_sync(', 1)[0] + r'''
char current_media_path[512];
static pthread_mutex_t net_mx=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t net_cv=PTHREAD_COND_INITIALIZER;
static int blocked,entered,release_net;
int evo_net_http_get_sync(const char *url,const char **h,int hn,char **out,size_t *n,int *status){
 (void)url;(void)h;(void)hn;pthread_mutex_lock(&net_mx);
 if(blocked){entered=1;pthread_cond_broadcast(&net_cv);
  while(!release_net)pthread_cond_wait(&net_cv,&net_mx);}
 pthread_mutex_unlock(&net_mx);
 *out=strdup("1\n00:00:05,000 --> 00:00:09,000\nOnline A\n\n");*n=strlen(*out);*status=200;return 0;
}
double evo_pb_position_s(void){return 6;}
int prospero_request_inplace_seek(double seconds,int paused){(void)seconds;(void)paused;return 1;}
extern void pick_local(const char *path,int kind);
'''
        pump = source_file('core/src/screens/PlayerScreen.cpp').split(
            'static void pumpOnlineSubtitles()\n{', 1)[1].split('\nvoid PlayerScreen::update(', 1)[0]
        pump = pump.replace('    prospero_subtitle_use_external = 1;\n    prospero_subtitle_enabled = 1;',
                            '    prospero_subtitle_select_primary(-1);')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for relative in ('include/evo_ntfs.h', 'include/evo_boot_log.h', 'include/evo_data_path.h',
                             'media/include/evo_subtitle.h', 'media/include/evo_langpref.h',
                             'media/include/evo_charset.h', 'media/include/evo_audio_out.h',
                             'media/include/evo_subsync.h', 'media/include/evo_demux.h',
                             'media/include/evo_playback.h', 'media/include/evo_packet_queue.h',
                             'addons/include/evo_online_subs.h', 'addons/include/cJSON.h',
                             'addons/src/cJSON.c', 'addons/include/evo_net.h', 'media/include/evo_langname.h'):
                (directory / Path(relative).name).write_text(source_file(relative))
            (directory / 'ps5-preferences.h').write_text((ROOT / 'scripts/ps5-preferences.h').read_text())
            (directory / 'preferences.c').write_text((ROOT / 'scripts/ps5-preferences.c').read_text())
            online_header = directory / 'evo_online_subs.h'
            online_header.write_text(online_header.read_text().replace(
                'int  evo_osubs_fetching(void);',
                'int  evo_osubs_fetching(void);\nvoid evo_osubs_cancel_fetch(void);'))
            cpp = directory / 'local.cpp'
            cpp.write_text(r'''
#include <string>
#include <vector>
#include "evo_subtitle.h"
#include "evo_online_subs.h"
#define EVO_LOGW(...) ((void)0)
#define EVO_LOGI(...) ((void)0)
enum {EVO_FB_BOUNDARY,EVO_FB_CONFIRM,EVO_FB_ERROR};
void evo_feedback(int){}
void toast(const char *,const char *){}
enum class ScreenId {Player};
struct ScreenManager {void navigateTo(ScreenId){}};
struct Application {
 static Application& getInstance(){static Application app;return app;}
 ScreenManager* getScreenManager(){static ScreenManager sm;return &sm;}
};
struct SubtitleFileScreen {
 struct Row {std::string path,name;bool isDir;};
 int m_selectedIndex=0;
 std::vector<Row> m_rows;
 std::vector<int> m_stack;
 std::string m_placeLabel;
 void openFolder(const std::string&,const std::string&){}
 void activate();
};
''' + activate + r'''
extern "C" void pick_local(const char *path,int kind){
 SubtitleFileScreen screen;screen.m_rows.push_back({path,"Fixture",kind==1});
 if(kind==2)screen.m_selectedIndex=-1;
 screen.activate();
}
static void pumpOnlineSubtitles(){
''' + pump + r'''
extern "C" void pump_online(){pumpOnlineSubtitles();}
''')
            obj = directory / 'local.o'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', tmp,
                            *flags.stdout.split(' -l', 1)[0].split(),
                            '-c', str(cpp), '-o', str(obj)], check=True, timeout=30)
            source = prelude + subtitle + source_file('media/src/evo_langpref.c') + \
                subtitle_handoff.patch_online_source(source_file('addons/src/evo_online_subs.c')) + r'''
extern void pump_online(void);
int main(int argc,char **argv){
 assert(argc==3);test_directory=argv[1];play_fmt=avformat_alloc_context();assert(play_fmt);
 nuvio_preferences_t policy={.valid=1};nuvio_preferences_import("one",&policy,NULL,0);
 evo_osubs_begin("web:one");evo_osubs_add("web:one","https://subs.invalid/a.srt","en","Fixture");
 assert(evo_osubs_fetch_async(0)==0);while(evo_osubs_fetching())usleep(1000);pump_online();
 assert(evo_osubs_active()==0 && prospero_subtitle_use_external);
 const ProsperoSubtitleCue *cue=prospero_subtitle_active_cue(6);assert(cue && !strcmp(cue->text,"Online A"));
 char local[1024];snprintf(local,sizeof local,"%s/local.srt",test_directory);
 FILE *f=fopen(local,"wb");assert(f);assert(fputs("1\n00:00:05,000 --> 00:00:09,000\nLocal B\n\n",f)>=0);assert(!fclose(f));
 int pending=!strcmp(argv[2],"pending");
 if(pending){
  pthread_mutex_lock(&net_mx);blocked=1;pthread_mutex_unlock(&net_mx);
  assert(evo_osubs_fetch_async(0)==0);
  pthread_mutex_lock(&net_mx);while(!entered)pthread_cond_wait(&net_cv,&net_mx);pthread_mutex_unlock(&net_mx);
 }
 // Directory, out-of-range and unreadable-file attempts do not relinquish A.
 pick_local(local,1);pick_local(local,2);pick_local("/no-such-nuvio-fixture.srt",0);
 assert(evo_osubs_active()==0);
 assert(evo_osubs_fetching()==pending);
 pick_local(local,0);
 if(pending){
  pthread_mutex_lock(&net_mx);release_net=1;pthread_cond_broadcast(&net_cv);pthread_mutex_unlock(&net_mx);
  while(evo_osubs_fetching())usleep(1000);
  pump_online(); // Execute the real completion consumer, not just take_ready.
  cue=prospero_subtitle_active_cue(6);assert(cue && !strcmp(cue->text,"Local B"));
 }
 nuvio_preferences_snapshot reopen;nuvio_preferences_capture(&reopen,0);
 assert(!strcmp(reopen.path,local));
 nuvio_preferences_subtitles(play_fmt,0,&reopen);
 cue=prospero_subtitle_active_cue(6);assert(cue && !strcmp(cue->text,"Local B"));
 assert(prospero_subtitle_use_external && prospero_subtitle_enabled && evo_osubs_active()==-1);
 prospero_embedded_subtitle_close();avformat_free_context(play_fmt);
 printf("local ownership: %s retained B after actual picker, completion pump and reopen\n",argv[2]);return 0;
}
'''
            for scenario in ('reopen', 'pending'):
                with self.subTest(scenario=scenario):
                    result = compile_run(source, tmp, [directory, scenario], extra_flags=[
                        '-D_DEFAULT_SOURCE', '-I', tmp, '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                        str(directory / 'cJSON.c'), str(directory / 'preferences.c'), str(obj),
                        '-lstdc++', '-pthread', *flags.stdout.split()])
                    self.assertIn('retained B after actual picker, completion pump and reopen', result)


if __name__ == '__main__':
    unittest.main()
