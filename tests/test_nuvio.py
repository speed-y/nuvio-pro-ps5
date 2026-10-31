"""Exercise range playback and confinement on the actual host HTTP handler."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

APP = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(APP))
spec = importlib.util.spec_from_file_location('nuvio_build', APP/'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
# serve's sibling import is isolated to this module load.
spec = importlib.util.spec_from_file_location('nuvio_serve', APP/'serve.py')
serve = importlib.util.module_from_spec(spec)
old = sys.modules.get('build')
sys.modules['build'] = build
try:
    spec.loader.exec_module(serve)
finally:
    if old is None:
        del sys.modules['build']
    else:
        sys.modules['build'] = old


class NuvioHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)/'ui'
        root.mkdir()
        (root/'index.html').write_bytes(b'NUVIO fixture')
        outside = Path(self.tmp.name)/'outside.txt'
        outside.write_bytes(b'not served')
        (root/'escape.txt').symlink_to(outside)
        self.clip = Path(self.tmp.name)/'clip.mp4'
        self.clip.write_bytes(bytes(range(256)))
        self.server = serve.server(root, self.clip, '127.0.0.1', 0, 'http://fixture.invalid')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def get(self, path, value=None, method='GET'):
        headers = {'Range': value} if value else {}
        return urllib.request.urlopen(urllib.request.Request(self.url+path, headers=headers, method=method), timeout=2)

    def test_seek_ranges_and_head(self):
        for value, expected in [('bytes=10-19',bytes(range(10,20))),('bytes=250-',bytes(range(250,256))),('bytes=-3',bytes(range(253,256)))]:
            with self.get('/ps5-test/clip.mp4', value) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), expected)
        with self.get('/ps5-test/clip.mp4','bytes=10-19','HEAD') as response:
            self.assertEqual(response.headers['Content-Length'],'10')
            self.assertEqual(response.read(),b'')

    def test_invalid_ranges_and_confinement(self):
        for value in ('bytes=256-', 'bytes=20-10', 'bytes=-0', 'bytes=1-2,4-5', 'bytes=-'):
            with self.assertRaises(urllib.error.HTTPError) as exc:
                self.get('/ps5-test/clip.mp4',value)
            self.assertEqual(exc.exception.code,416)
        for path in ('/%2e%2e/outside.txt','/escape.txt'):
            with self.assertRaises(urllib.error.HTTPError) as exc:
                self.get(path)
            self.assertEqual(exc.exception.code,403)

    def test_catalog_and_stream_contract(self):
        import json
        with self.get('/ps5-test/catalog/movie/ps5-test.json') as response:
            item = json.load(response)['metas'][0]
        with self.get('/ps5-test/stream/movie/'+item['id']+'.json') as response:
            self.assertEqual(json.load(response)['streams'][0]['url'], 'http://fixture.invalid/ps5-test/clip.mp4')
            self.assertEqual(response.headers['Access-Control-Allow-Origin'],'*')
        with self.get('/') as response:
            self.assertEqual(response.read(),b'NUVIO fixture')


class PS5InputTests(unittest.TestCase):
    def test_triangle_opens_search_input_without_bypassing_dialogs_or_profiles(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let route='home',modal=false,overlay=false,selected=null,navigations=0,release,inGesture=false;
const input={id:'searchInput',isConnected:true,getAttribute:()=>null,getClientRects:()=>[{}],
 matches:()=>true,contains:()=>false,
 focus(){assert.equal(inGesture,true,'Input focus must not wait for navigation');selected=this;}};
const screen={container:{querySelector:s=>s==='#searchInput'?input:
 s.includes('overlay')?(overlay?{}:null):selected},focusNode:(old,node)=>{selected=node;}};
const events={};
const Router={getCurrent:()=>route,getCurrentScreen:()=>screen,
 async navigate(next){navigations++;route=next;await new Promise(resolve=>release=resolve);}};
const context={Router,__NUVIO_PS5__:true,window:{addEventListener:(type,fn)=>events[type]=fn},
 initPs5SearchKeyboard(){},requestPs5SearchKeyboard(){},
 document:{hidden:false,body:{classList:{contains:()=>modal}}},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^import .*$/mg,'')
 .replace('export function','function')+'\ninitPs5Navigation();',context);
const settle=()=>new Promise(setImmediate);
(async()=>{
 for(const blocked of ['profileSelection','authQrSignIn','experienceModeSelection','player']) {
  route=blocked;events['nuvio:controller-menu']();await settle();assert.equal(navigations,0);
 }
 route='detail';modal=true;events['nuvio:controller-menu']();await settle();
 modal=false;overlay=true;events['nuvio:controller-menu']();await settle();
 assert.equal(navigations,0);overlay=false;
 inGesture=true;
 events.keydown({key:'F1',keyCode:112,preventDefault(){},stopImmediatePropagation(){}});
 inGesture=false;
 assert.equal(route,'search');assert.equal(selected,input);assert.equal(navigations,1);
 events['nuvio:controller-menu'](); // A duplicate while navigation completes is ignored.
 release();await settle();assert.equal(navigations,1);
 // Already on Search: refocus synchronously without remounting or clearing text.
 input.value='asymmetric query';selected=null;inGesture=true;
 events['nuvio:controller-menu']();inGesture=false;await settle();
 assert.equal(navigations,1);assert.equal(input.value,'asymmetric query');assert.equal(selected,input);
 selected=null;
 events.keydown({key:'F1',keyCode:112,repeat:true,preventDefault(){},stopImmediatePropagation(){}});
 await settle();assert.equal(selected,null);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        subprocess.run([node,'-e',script,str(APP/'ps5-navigation.js')],check=True,timeout=10)

    def test_x_activates_screen_or_modal_focus_once(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable; HTTP tests still run without it')
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let listener,focused=null,overlay=null,modal=false,dialog=null,stopped=0;
const body={classList:{contains:()=>modal},dispatchEvent(){}};
const screen={container:{classList:{contains:()=>false},querySelector:s=>s.includes('overlay')?overlay:focused}};
const listeners={};
const document={body,addEventListener:(name,fn)=>{listeners[name]=fn;listener=fn;},querySelectorAll:()=>dialog?[dialog]:[]};
const windowEvents={};
const context={window:{addEventListener:(name,fn)=>{windowEvents[name]=fn;}},document,__NUVIO_PS5__:true,
  initPs5SearchKeyboard(){},requestPs5SearchKeyboard(){},
  Router:{getCurrentScreen:()=>screen},KeyboardEvent:class{constructor(type,init){Object.assign(this,init);this.type=type;this.keyCode=0;this.which=0;}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8').replace(/^import .*$/mg,'').replace('export function','function')+'\ninitPs5Navigation();',context);
const e=(target={})=>({button:0,target,preventDefault(){stopped++;},stopImmediatePropagation(){stopped++;}});
function node(text=false){return {events:[],clicks:0,isConnected:true,disabled:false,dataset:{},closest:()=>null,
  getAttribute:()=>null,getClientRects:()=>[{}],matches:()=>text,focus(){this.domFocused=true;},
  contains(target){return target===this;},
  click(){this.clicks++;listener(e(this));},dispatchEvent(e){assert.equal(e.keyCode,13);assert.equal(e.which,13);this.events.push(e.type);}};}
listener(e()); assert.equal(stopped,2); // No focus never activates the stationary pointer.
focused=node();listener(e());assert.deepEqual(focused.events,['keydown','keyup']);
let pointerPrevented=false;context.window.__nuvioPs5PointerDown({button:0,target:{},preventDefault(){pointerPrevented=true;}});
assert.equal(pointerPrevented,true);
listener(e(focused));assert.equal(focused.events.length,4); // Pointer on focus also activates once.
listener({...e(),button:2});assert.equal(focused.events.length,4);
modal=true;const button=node();dialog={classList:{contains:()=>false},querySelector:()=>button};
listener(e());assert.deepEqual(button.events,['keydown','keyup']);assert.equal(focused.events.length,4);
dialog.querySelector=()=>null;listener(e());assert.equal(focused.events.length,4); // Modal mounting.
dialog.classList.contains=()=>true;listener(e());assert.equal(focused.events.length,4); // Modal exiting.
modal=false;const field=node(true);overlay={querySelector:()=>field};listener(e());
assert.equal(field.domFocused,true);assert.equal(field.clicks,1);assert.equal(focused.events.length,4);
field.disabled=true;listener(e());assert.equal(field.clicks,1); // Disabled overlay cannot fall through.
overlay=null;focused.isConnected=false;listener(e());assert.equal(focused.events.length,4);
// Cards moving beneath a stationary pointer must not replace controller focus.
const selected=node(),underPointer=node();focused=selected;
for(const type of ['mouseover','mouseenter','mousemove','pointerover','pointerenter','pointermove']) {
  let blocked=false;
  listeners[type]?.({target:underPointer,stopImmediatePropagation(){blocked=true;}});
  if(!blocked) focused=underPointer; // Screen hover handler would select this card.
  listeners.click(e());
  assert.equal(focused,selected,`${type} replaced controller focus`);
}
assert.equal(selected.events.length,12);assert.equal(underPointer.events.length,0);
// Observed Square/Options events open actions without activating playback.
(async()=>{
  for(const target of ['continueWatching','episode','playDefault']) {
    focused=node();focused.dataset.action=target;
    screen.isHomeHoldTarget=n=>n.dataset.action==='continueWatching';
    screen.isEpisodeHoldTarget=n=>n.dataset.action==='episode';
    const showMenu=()=>{modal=true;dialog={classList:{contains:()=>false},querySelector:()=>button};};
    screen.openHoldMenuForNode=screen.openEpisodeHoldMenu=screen.openHeroPlayMenu=showMenu;
    for(const event of [{key:'F2',keyCode:113},{key:'F3',keyCode:114},{key:'',keyCode:113}]) {
      const keyEvent={...e(),...event};
      windowEvents.keydown?.({...keyEvent,repeat:true});assert.equal(modal,false);
      windowEvents.keydown?.(keyEvent);
      assert.equal(modal,true,`${target} must offer actions on ${event.key || event.keyCode}`);
      assert.deepEqual(focused.events,[]); // No background playback activation.
      const previous=button.events.length;listener(e());
      assert.equal(button.events.length,previous+2); // X operates the menu.
      await new Promise(setImmediate);
      modal=false;
    }
  }
  focused=node(true);windowEvents.keydown?.({...e(),key:'F2',keyCode:113});
  assert.equal(modal,false); // Do not interrupt text entry with a page menu.
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        subprocess.run([node, '-e', script, str(APP/'ps5-input.js'), str(APP/'ps5-navigation.js')], check=True, timeout=10)

    def test_native_button_poll_does_not_replay_stale_presses(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let request,timer,modal=false,focused=true;const events=[],keys=[];
function target(name){return {isConnected:true,getAttribute:()=>null,getClientRects:()=>[1],
 dispatchEvent:e=>keys.push([name,e.type,e.key,e.keyCode,e.which])};}
const page=target('page'),dialog=target('dialog');
const document={hidden:false,body:{classList:{contains:()=>modal}},
 querySelectorAll:()=>[{classList:{contains:()=>false},querySelector:()=>focused?dialog:null}]};
const context={__NUVIO_PS5__:true,document,Event:class{constructor(type){this.type=type;}},
 KeyboardEvent:class{constructor(type,init){this.type=type;this.key=init.key;this.keyCode=0;this.which=0;}},
 Router:{getCurrentScreen:()=>({container:{querySelector:s=>s==='.focused'&&focused?page:null}})},
  initPs5SearchKeyboard(){},requestPs5SearchKeyboard(){},
  window:{__evoHook:true,addEventListener(){},dispatchEvent:e=>events.push(e.type)},
  setTimeout:fn=>{timer=fn;},XMLHttpRequest:class{constructor(){request=this;}open(){}send(){}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^import .*$/mg,'').replace('export function','function')+'\ninitPs5Navigation();',context);
function response(options,menu,status=200,navigation=0,direction=0){request.status=status;request.responseText=JSON.stringify({options,menu,navigation,direction});request.onload();request.onloadend();timer();}
response(7,2);assert.deepEqual(events,[]); // Establish a baseline, not seven old presses.
response(8,2);assert.deepEqual(events,['nuvio:options']);
response(8,2);assert.equal(events.length,1); // A held native button does not replay.
response(8,3);assert.deepEqual(events,['nuvio:options','nuvio:controller-menu']);
response(9,3,503);response(10,3);assert.equal(events.length,2); // Reconnect discards old edges.
document.hidden=true;response(11,3);document.hidden=false;timer();response(12,3);
assert.equal(events.length,2); // Backgrounding and a late response cannot queue a menu.
response(13,3);assert.equal(events.length,3);
for(const [sequence,direction,key,code] of [[1,2,'ArrowRight',39],[2,1,'ArrowUp',38],
 [3,4,'ArrowLeft',37],[4,3,'ArrowDown',40]]) {
 response(13,3,200,sequence,direction);
 assert.deepEqual(keys.slice(-2),[['page','keydown',key,code,code],['page','keyup',key,code,code]]);
}
assert.equal(keys.length,8);
response(13,3,200,4,3);assert.equal(keys.length,8); // No replay on unchanged counter.
response(13,3,200,20,2);assert.equal(keys.length,10); // Coalesce delayed repeats, not a burst.
modal=true;response(13,3,200,21,4);
assert.deepEqual(keys.slice(-2),[['dialog','keydown','ArrowLeft',37,37],['dialog','keyup','ArrowLeft',37,37]]);
focused=false;response(13,3,200,22,1);assert.equal(keys.length,12); // Never navigate the page behind an unready dialog.
focused=true;response(13,3,200,23,9);assert.equal(keys.length,12); // Invalid direction ignored.
response(13,3,503,24,1);response(13,3,200,25,1);assert.equal(keys.length,12);
document.hidden=true;response(13,3,200,26,1);document.hidden=false;timer();
response(13,3,200,27,1);assert.equal(keys.length,12); // Baseline after resume, no queued navigation.
response(13,3,200,28,3);assert.equal(keys.length,14);
"""
        subprocess.run([node, '-e', script, str(APP/'ps5-navigation.js')], check=True, timeout=10)


class PS5SearchKeyboardTests(unittest.TestCase):
    def test_native_search_accept_cancel_failure_and_stale_route(self):
        import subprocess
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let route='search',statuses=[],requests=[],changes=[],statusNode=null,release;
const input={isConnected:true,value:'Initial & query',dispatchEvent:e=>changes.push([e.type,input.value]),
 closest:()=>({insertAdjacentElement:(where,node)=>{statusNode=node;}})};
const submissions=[];
const screen={container:{querySelector:s=>s==='#searchInput'?input:statusNode},
 cancelScheduledInputSearch(){},runSearchFromInput:async(node,options)=>submissions.push([node.value,options.autoFocusResults])};
const events={};
const context={__NUVIO_PS5__:true,Router:{getCurrent:()=>route,getCurrentScreen:()=>screen},
 window:{__evoHook:true,addEventListener:(name,fn)=>events[name]=fn},
 document:{hidden:false,createElement:()=>({style:{},setAttribute(){},remove(){statusNode=null;}})},
 URLSearchParams,Event:class{constructor(type){this.type=type;}},setTimeout:fn=>setImmediate(fn),
 fetch:async url=>{requests.push(url);const next=statuses.shift();assert(next,'Unexpected request');
   if(next.wait)await new Promise(resolve=>release=resolve);
   return {status:next.status,text:async()=>next.text};}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^import .*$/mg,'')
 .replace(/export /g,'')+'\ninitPs5SearchKeyboard();',context);
const settle=()=>new Promise(setImmediate);
(async()=>{
 statuses=[{status:202},{status:200,text:'Amélie & 東京'}];
 await context.requestPs5SearchKeyboard();
 assert.equal(requests[0],'/evo/text-input?open=Initial%20%26%20query');
 assert.equal(requests[1],'/evo/text-input');
 assert.equal(input.value,'Amélie & 東京');assert.deepEqual(changes,[['input','Amélie & 東京']]);
 statuses=[{status:204}];await context.requestPs5SearchKeyboard();
 assert.equal(input.value,'Amélie & 東京');assert.equal(changes.length,1);
 statuses=[{status:503}];await context.requestPs5SearchKeyboard();
 assert(statusNode.textContent.includes('could not open'));assert.equal(changes.length,1);
 statuses=[{status:200,text:'stale',wait:true}];
 const pending=context.requestPs5SearchKeyboard();await settle();
 const count=requests.length;await context.requestPs5SearchKeyboard();assert.equal(requests.length,count);
 route='home';release();await pending;assert.equal(input.value,'Amélie & 東京');
 // Returning from result details preserves results without opening native IME.
 route='search';const beforeBack=requests.length;
 await context.requestPs5SearchKeyboard({isBackNavigation:true});
 assert.equal(requests.length,beforeBack);assert.equal(input.value,'Amélie & 東京');
 // A later explicit textbox request still opens the keyboard on that same page.
 route='search';statuses=[{status:204}];events.click({target:{id:'searchInput'}});await settle();
 assert.equal(statuses.length,0);
 assert.equal(events.focusin,undefined); // Rerenders and D-pad focus never open IME.
 context.window.__evoHook=false;await context.requestPs5SearchKeyboard();
 assert.equal(requests.length,count+1); // Desktop previews never request PS5 IME.
 // Save the exact query/profile before browser closure.
 context.window.__evoHook=true;const saved=[];
 context.window.location={search:''};
 context.Router.persistWebOsResumeRoute=(route,params)=>saved.push([route,params.query]);
 context.window.__nuvioSavePlaybackReturn=()=>saved.push('profile');
 context.window.__nuvioPrepareKeyboard=()=>saved.push('flush');
 statuses=[{status:204}];await context.requestPs5SearchKeyboard();
 assert.deepEqual(saved,[['search','Amélie & 東京'],'profile','flush']);
 // Recreated Search reads the result once; later explicit requests work again.
 context.window.location.search='?nuvioPlaybackReturn=1&nuvioKeyboardReturn=1';
 statuses=[{status:200,text:'Arrival'}];await context.requestPs5SearchKeyboard();
 assert.equal(requests.at(-1),'/evo/text-input');assert.equal(input.value,'Arrival');
 assert.deepEqual(submissions.at(-1),['Arrival',true]);
 statuses=[{status:204}];await context.requestPs5SearchKeyboard();
 assert.equal(requests.at(-1),'/evo/text-input?open=Arrival');assert.equal(saved.length,6);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        subprocess.run(['node','-e',script,str(APP/'ps5-text-input.js')],check=True,timeout=10)

    def test_native_endpoint_accepts_cancels_and_refuses_without_fallback(self):
        import subprocess
        import tempfile
        source = r'''
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
enum {P_RUN=1,P_CLOSING=2,P_PLAYING=3,CDLG_STATUS_NONE=0,CDLG_STATUS_INITIALIZED=1,CDLG_STATUS_RUNNING=2,CDLG_STATUS_FINISHED=3};
static pthread_mutex_t s_mx=PTHREAD_MUTEX_INITIALIZER;
static const char *s_hook_profile="nuvio";
static int active=1,available=1,opened=0,finish=0;
static int s_state=P_RUN,s_closed_by_evo,webstatus=2,imestatus=0,nativeCalls=0;
static char s_reopen_url[2048],s_open_url[2048]="http://127.0.0.1:8686/";
static void (*submit)(const char *,void *);
static char status[64],body[1024];
static int sceWebBrowserDialogClose(void){return active?0:-1;}
static int sceWebBrowserDialogUpdateStatus(void){return webstatus;}
static int sceImeDialogGetStatus(void){return imestatus;}
static int evo_keyboard_is_open(void){return opened;}
static int evo_keyboard_open_native(const char *title,const char *text,int max,
                                   void (*cb)(const char *,void *),void *data){
 (void)title;(void)text;(void)max;(void)data;
 assert(webstatus!=2);nativeCalls++;submit=cb;imestatus=available;return opened=available;
}
static void evo_keyboard_update(void){
 if(finish){opened=0;imestatus=0;if(finish==1)submit("Amélie & 東京",NULL);finish=0;}
}
static int query_param(const char *path,const char *key,char *out,size_t cap){
 (void)key;const char *value=strstr(path,"?open=");
 snprintf(out,cap,"%s",value?value+6:"");return value!=NULL;
}
static void respond(int fd,const char *s,const char *type,const char *b,size_t n){
 (void)fd;(void)type;snprintf(status,sizeof status,"%s",s);
 assert(n<sizeof body);memcpy(body,b,n);body[n]=0;
}
static void tlog(const char *fmt,...){(void)fmt;}
#include "ps5-text-input.c"
#include "ps5-text-input-session.c"
static void open_dialog(const char *url){assert(imestatus==0);assert(strstr(url,"nuvioKeyboardReturn=1"));s_state=P_RUN;webstatus=2;}
static void read_result(void){assert(s_closed_by_evo);}
static void pump_open(void){
 text_input_session_pump();int calls=nativeCalls;text_input_session_pump();assert(nativeCalls==calls);
 webstatus=3;text_input_session_pump();
}
static void pump_finish(void){text_input_session_pump();text_input_session_pump();}
int main(void){
 text_input_serve(0,"/evo/text-input?open=initial");assert(!strcmp(status,"202 Accepted"));
 pump_open();text_input_serve(0,"/evo/text-input?open=duplicate");
 assert(!strcmp(status,"409 Conflict"));
 text_input_serve(0,"/evo/text-input");assert(!strcmp(status,"202 Accepted"));
 finish=1;pump_finish();text_input_serve(0,"/evo/text-input");
 assert(!strcmp(status,"200 OK"));assert(!strcmp(body,"Amélie & 東京"));
 text_input_serve(0,"/evo/text-input?open=");pump_open();finish=2;pump_finish();
 text_input_serve(0,"/evo/text-input");assert(!strcmp(status,"204 No Content"));assert(!*body);
 available=0;text_input_serve(0,"/evo/text-input?open=retry");pump_open();text_input_session_pump();
 text_input_serve(0,"/evo/text-input");assert(!strcmp(status,"503 Service Unavailable"));assert(!*body);
 available=1;text_input_serve(0,"/evo/text-input?open=retry");pump_open();
 text_input_serve(0,"/evo/text-input");assert(!strcmp(status,"202 Accepted"));
 /* There is no typing timeout, even after five minutes. */
 s_text_started.tv_sec-=300;text_input_session_pump();assert(opened);
 finish=2;pump_finish();active=0;
 text_input_serve(0,"/evo/text-input?open=inactive");text_input_session_pump();
 text_input_serve(0,"/evo/text-input");assert(!strcmp(status,"503 Service Unavailable"));
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'keyboard.c'
            path.write_text(source)
            (Path(directory)/'evo_ime_dialog.h').write_text('enum { SCE_IME_DIALOG_STATUS_NONE=0 };\n')
            binary=Path(directory)/'keyboard'
            subprocess.run(['cc','-std=c11','-D_POSIX_C_SOURCE=200809L','-Wall','-Wextra','-Werror','-pthread',
                            '-I',directory,'-I',str(APP),str(path),'-o',str(binary)],check=True,timeout=20)
            subprocess.run([str(binary)],check=True,timeout=10)


class ProviderSeekTests(unittest.TestCase):
    def test_provider_without_local_path_queues_seek(self):
        import shutil
        import subprocess
        compiler=shutil.which('clang') or shutil.which('cc')
        if not compiler:
            self.skipTest('No host C compiler')
        demux=(APP.parent/'tests/fixtures/nuvio_seek.c.txt').read_text()
        controller=('    if (!prospero_request_inplace_seek(targetSeconds, 0)) {\n'
                    '        return;\n'
                    '    }\n'
                    '    pp_playback_notify_seek_begin(&g_pp_pb, targetUs);')
        fixed,_=build.fix_provider_seek(demux,controller)
        harness=r"""
#include <assert.h>
#include <pthread.h>
static void *play_fmt=(void *)1;
static int video_stream_index=0,audio_stream_index=-1;
static char current_media_path[1]={0};
static double media_duration_sec=100,prospero_seek_target_seconds;
static int player_paused,controls_last_used_ms,prospero_seek_restore_paused,prospero_seek_pending;
static pthread_mutex_t prospero_seek_mutex=PTHREAD_MUTEX_INITIALIZER;
static int now_ms(void) {return 1;}
"""+fixed+r"""
int main(void) {
 (void)controls_last_used_ms;
 assert(current_media_path[0]==0);
 assert(prospero_request_inplace_seek(30,0)==1);
 assert(prospero_seek_pending==1 && prospero_seek_target_seconds==30 && player_paused);
 assert(prospero_request_inplace_seek(200,1)==1);
 assert(prospero_seek_target_seconds==99 && prospero_seek_restore_paused==1);
 play_fmt=0;prospero_seek_pending=0;player_paused=0;
 assert(prospero_request_inplace_seek(40,0)==0);
 assert(!prospero_seek_pending && !player_paused);
 play_fmt=(void *)1;video_stream_index=-1;
 assert(prospero_request_inplace_seek(40,0)==0);
 return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'seek.c';source.write_text(harness)
            binary=Path(tmp)/'seek'
            subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-pthread',str(source),'-o',str(binary)],check=True,timeout=20)
            subprocess.run([str(binary)],check=True,timeout=10)

    def test_provider_seek_contract_move_is_refused(self):
        # v0.12.0 drops the demuxer's local-path requirement and resumes a
        # refused seek in the controller. A revision that restores the old
        # guard, or moves the controller contract, must stop the build.
        legacy=('int prospero_request_inplace_seek(double t, int r) {\n'
                '    if (\n'
                '        !play_fmt ||\n'
                '        (video_stream_index < 0 && audio_stream_index < 0) ||\n'
                '        !current_media_path[0]\n'
                '    ) {\n'
                '        return 0;\n'
                '    }\n'
                '    return 1;\n'
                '}')
        controller=('    if (!prospero_request_inplace_seek(targetSeconds, 0)) {\n'
                    '        return;\n'
                    '    }\n'
                    '    pp_playback_notify_seek_begin(&g_pp_pb, targetUs);')
        with self.assertRaises(RuntimeError):
            build.fix_provider_seek(legacy, controller)
        with self.assertRaises(RuntimeError):
            build.fix_provider_seek(
                '        (video_stream_index < 0 && audio_stream_index < 0)\n    ) {',
                'controller without the pinned anchors')


class LoopbackDiagnosticAdapterTests(unittest.TestCase):
    def test_proxy_reports_each_socket_stage_and_browser_connection(self):
        source = '''    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) { LOG("server: socket errno=%d", errno); return; }
    if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0 || listen(fd, 16) != 0) {
        LOG("server: bind/listen 127.0.0.1:%d failed errno=%d", s_port, errno);
        close(fd);
        return;
    }
        int c = accept(s_listen_fd, NULL, NULL);
        if (c >= 0 && s_srv_stop) { close(c); break; }'''
        adapted = build.instrument_loopback_server(source)
        for result in ('socket failed errno=%d', 'socket ok fd=%d',
                       'bind failed port=%d errno=%d', 'bind ok 127.0.0.1:%d',
                       'listen failed port=%d errno=%d', 'listen ok port=%d',
                       'connection accepted'):
            self.assertIn(result, adapted)

    def test_proxy_diagnostic_refuses_moved_anchor(self):
        with self.assertRaises(RuntimeError):
            build.instrument_loopback_server('int fd = socket(AF_INET, SOCK_STREAM, 0);')

    def test_unpromoted_diagnostic_bypasses_only_the_missing_origin_preflight(self):
        source = '''    case P_CHECK:
        if (s_check_rc == 0) return;
        if (s_check_rc < 0) {
            char m[256];
'''
        adapted = build.bypass_loopback_origin_preflight(source)
        self.assertIn('preflight bypassed for unpromoted loopback diagnostic', adapted)
        self.assertNotIn('#ifdef NUVIO_UNPROMOTED_LOOPBACK_DIAGNOSTIC', adapted)
        self.assertIn('if (s_check_rc < 0) {\n            char m[256];', adapted)

    def test_unpromoted_diagnostic_refuses_moved_preflight_anchor(self):
        with self.assertRaises(RuntimeError):
            build.bypass_loopback_origin_preflight('case P_CHECK: break;')


class FFmpegProfileTests(unittest.TestCase):
    def test_profile_keeps_evo_minimum_and_drops_dav1d(self):
        # The FFmpeg stage must keep the components the port relies on, keep the
        # native AV1 decoder out, and keep the deliberate no-dav1d policy; a
        # drifted flag list would change format support silently.
        for flag in ('--disable-everything', '--enable-swscale', '--enable-network',
                     '--enable-openssl', '--enable-libxml2', '--enable-decoder=hevc',
                     '--enable-decoder=truehd', '--enable-demuxer=matroska',
                     '--enable-demuxer=hls', '--enable-protocol=crypto',
                     '--enable-parser=av1', '--enable-bsf=av1_frame_merge'):
            self.assertIn(flag, build.FFMPEG_FLAGS)
        self.assertNotIn('--enable-decoder=av1', build.FFMPEG_FLAGS)
        self.assertEqual([f for f in build.FFMPEG_FLAGS if 'dav1d' in f], [])


class ControlEvidenceTests(unittest.TestCase):
    def test_upload_success_does_not_mask_launch_refusal(self):
        import contextlib
        import io
        import types
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('nuvio_install',APP/'install.py')
        installer=importlib.util.module_from_spec(spec)
        previous=sys.modules.get('build');sys.modules['build']=build
        try:spec.loader.exec_module(installer)
        finally:
            if previous is None:del sys.modules['build']
            else:sys.modules['build']=previous
        for text in ('NUVIO launch refused: close the running title', 'NUVIO launch_result=0x80940004', 'sent bytes'):
            result=types.SimpleNamespace(returncode=0,stdout=text,stderr='')
            with patch.object(installer.subprocess,'run',return_value=result),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):installer.helper(3,'fixture.invalid')
        result=types.SimpleNamespace(returncode=0,stdout='NUVIO launch_result=0x8018',stderr='')
        with patch.object(installer.subprocess,'run',return_value=result),contextlib.redirect_stdout(io.StringIO()):
            self.assertIn('0x8018',installer.helper(3,'fixture.invalid'))
        result=types.SimpleNamespace(returncode=0,stdout='NUVIO eboot stage=absent',stderr='')
        with patch.dict(installer.os.environ,{'PS5_READ_IDLE_TIMEOUT':'3'}), \
             patch.object(installer.subprocess,'run',return_value=result) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            installer.helper(5,'fixture.invalid')
            self.assertEqual(run.call_args.kwargs['env']['PS5_READ_IDLE_TIMEOUT'],'60.0')
            self.assertGreater(run.call_args.kwargs['timeout'],60+5+30+10)
        with patch.dict(installer.os.environ,{'PS5_READ_IDLE_TIMEOUT':'120'}), \
             patch.object(installer.subprocess,'run',return_value=result) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            installer.helper(5,'fixture.invalid')
            self.assertEqual(run.call_args.kwargs['env']['PS5_READ_IDLE_TIMEOUT'],'120.0')
            self.assertGreater(run.call_args.kwargs['timeout'],120+5+30+10)


class UpdateMetadataTests(unittest.TestCase):
    def test_update_allows_only_a_content_version_bump(self):
        import json
        import update
        before={'titleId':'PPSA99996','contentId':'UP9000-PPSA99996_00-NUVIOPS500000000',
                'contentVersion':'01.000.001','localizedParameters':{'en-US':{'titleName':'Nuvio'}}}
        after={**before,'contentVersion':'01.000.002'}
        self.assertTrue(update.safe_param_update(json.dumps(before).encode(),
                                                 json.dumps(after).encode()))
        with_music={**after,'pubtools':{'loudnessSnd0':'-28.00'}}
        self.assertTrue(update.safe_param_update(json.dumps(before).encode(),
                                                 json.dumps(with_music).encode()))
        self.assertTrue(update.safe_param_update(json.dumps(with_music).encode(),
                                                 json.dumps(with_music).encode()))
        for pubtools in ({'loudnessSnd0':'0.00'},
                         {'loudnessSnd0':'-28.00','other':1}, None):
            self.assertFalse(update.safe_param_update(
                json.dumps(before).encode(), json.dumps({**after,'pubtools':pubtools}).encode()))
        self.assertFalse(update.safe_param_update(json.dumps(with_music).encode(),
                                                  json.dumps(after).encode()))
        # EVO v0.12.0 adds the flexible-memory declaration with the update.
        with_memory={**after,'kernel':{'flexibleMemorySize':1073741824}}
        self.assertTrue(update.safe_param_update(json.dumps(before).encode(),
                                                 json.dumps(with_memory).encode()))
        self.assertFalse(update.safe_param_update(
            json.dumps(with_memory).encode(),
            json.dumps({**after,'kernel':{'flexibleMemorySize':2097152}}).encode()))
        self.assertFalse(update.safe_param_update(
            json.dumps(before).encode(),
            json.dumps({**after,'kernel':{'flexibleMemorySize':1048577}}).encode()))
        self.assertFalse(update.safe_param_update(
            json.dumps(before).encode(),
            json.dumps({**after,'kernel':{'flexibleMemorySize':1073741824,'other':1}}).encode()))
        for change in ({'titleId':'PPSA11111'},
                       {'contentId':'UP9000-PPSA11111_00-NUVIOPS500000000'},
                       {'localizedParameters':{'en-US':{'titleName':'Other'}}},
                       {'contentVersion':'01.000.000'}):
            self.assertFalse(update.safe_param_update(json.dumps(before).encode(),
                                                      json.dumps({**before,**change}).encode()))

    def test_console_eboot_report_requires_installed_backup_and_stage(self):
        import update
        installed='a'*64
        backup='a'*64
        stage='b'*64
        output=(f'NUVIO eboot installed bytes=100 sha256={installed}\n'
                f'NUVIO eboot backup bytes=100 sha256={backup}\n'
                f'NUVIO eboot stage bytes=101 sha256={stage}\n')
        self.assertEqual(update.parse_eboot_report(output), {
            'installed':(100,installed),'backup':(100,backup),'stage':(101,stage)})
        absent=output.replace(f'NUVIO eboot stage bytes=101 sha256={stage}',
                              'NUVIO eboot stage=absent')
        self.assertIsNone(update.parse_eboot_report(absent)['stage'])
        with self.assertRaises(RuntimeError):
            update.parse_eboot_report('NUVIO eboot installed=unknown')

    def test_update_remote_dirs_lists_parent_chain(self):
        import update
        self.assertEqual(update.remote_dirs('/data/homebrew/PPSA99996/assets/hui/sfx/focus_01.wav'),
                         ['/data','/data/homebrew','/data/homebrew/PPSA99996','/data/homebrew/PPSA99996/assets','/data/homebrew/PPSA99996/assets/hui','/data/homebrew/PPSA99996/assets/hui/sfx'])
        self.assertEqual(update.remote_dirs('/x.txt'), [])

    def test_update_allowlist_covers_evo_assets_and_keeps_the_native_set(self):
        import update
        reviewed=['eboot.bin','sce_sys/param.json','webui/app.bundle.js','webui/css/bundle.css',
                  'assets/rml/launch.rml','assets/hui/sfx/focus_01.wav',
                  'assets/hui/fonts/inter-regular.huifont',
                  'sce_sys/pic0.dds','sce_sys/pic1.dds','sce_sys/snd0.at9']
        self.assertTrue(update.changes_are_reviewed(reviewed))
        self.assertFalse(update.changes_are_reviewed(['sce_module/libc.prx']))
        self.assertFalse(update.changes_are_reviewed(['assets/icons/other.png']))
        self.assertFalse(update.changes_are_reviewed(['sce_sys/other.at9']))


class RouteResumeTests(unittest.TestCase):
    def test_ps5_retains_previous_route_across_player_and_reload(self):
        import subprocess
        import shutil
        import polish
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'js/ui/navigation/routerMethods-02-complete-route-return-back-guard.js'
            target.parent.mkdir(parents=True)
            target.write_text((APP.parent/'tests/fixtures/router_resume.js.txt').read_text())
            target.write_text(polish.patch_resume_router(target.read_text()))
            script=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const store=new Map(),ctx={__NUVIO_PS5__:true,Platform:{isWebOS:()=>false},LocalStore:{set:(k,v)=>store.set(k,v),get:(k,d)=>store.get(k)||d,remove:k=>store.delete(k)},WEBOS_RESUME_ROUTE_KEY:'resume',WEBOS_RESUME_ROUTE_TTL_MS:60000,WEBOS_NON_RESTORABLE_ROUTES:new Set(['player','stream','detail']),console};
const router=vm.runInNewContext('({'+fs.readFileSync(process.argv[1],'utf8')+'})',ctx);
router.routes={streams:{},stream:{},detail:{},player:{},home:{}};
router.persistWebOsResumeRoute('streams',{id:'fixture'});
router.persistWebOsResumeRoute('player',{});
let restored=router.consumeWebOsResumeRoute();assert.equal(restored.route,'streams');assert.equal(restored.params.id,'fixture');
router.persistWebOsResumeRoute('detail',{id:'title'});assert.equal(router.consumeWebOsResumeRoute().route,'detail');
router.persistWebOsResumeRoute('stream',{id:'title'});assert.equal(router.consumeWebOsResumeRoute().route,'stream');
store.get('resume').savedAt=Date.now()-61000;assert.equal(router.consumeWebOsResumeRoute(),null);
ctx.__NUVIO_PS5__=false;router.persistWebOsResumeRoute('home',{});assert.equal(store.size,0);
"""
            subprocess.run([node,'-e',script,str(target)],check=True,timeout=10)


class CollectionSourceTests(unittest.TestCase):
    def test_nullable_rating_filters_survive_repeated_normalization(self):
        import polish
        import shutil
        import subprocess
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        source=(APP.parent/'tests/fixtures/collection_sources.js.txt').read_text()
        fixed=polish.patch_collection_filters(source)
        script=r"""
const vm=require('vm'),assert=require('assert');
const ctx={};vm.createContext(ctx);
vm.runInContext(process.argv[1].replace(/^export /mg,''),ctx);
for(const [input,expected] of [
 [undefined,[null,null,null]], [null,[null,null,null]],
 [{voteAverageGte:null,voteAverageLte:null,voteCountGte:null},[null,null,null]],
 [{voteAverageGte:0,voteAverageLte:0,voteCountGte:0},[0,0,0]],
 [{voteAverageGte:'6.75',voteAverageLte:8.25,voteCountGte:123.9},[6.75,8.25,123]],
 [{voteAverageGte:7.5,voteAverageLte:null,voteCountGte:321},[7.5,null,321]]
]) {
 let folder={sources:[{provider:'tmdb',tmdbSourceType:'DISCOVER',
  filters:input==null?input:{...input,withGenres:'18,9648',releaseDateGte:'2026-01-01'}}]};
 for(let pass=0;pass<4;pass++) {
  folder={sources:ctx.getCollectionFolderSources(JSON.parse(JSON.stringify(folder)))};
  const f=folder.sources[0].filters;
  assert.deepStrictEqual([f.voteAverageGte,f.voteAverageLte,f.voteCountGte],expected);
  if(input!=null) {
   assert.equal(f.withGenres,'18,9648');assert.equal(f.releaseDateGte,'2026-01-01');
  }
 }
}
"""
        subprocess.run([node,'-e',script,fixed],check=True,timeout=10)
        with self.assertRaises(RuntimeError):
            polish.patch_collection_filters('changed upstream')


class UIIndexTests(unittest.TestCase):
    def test_runtime_config_keeps_public_login_and_metadata_without_other_credentials(self):
        import json
        import re
        import zipfile
        from unittest.mock import patch
        official = {
            'NUVIO_SUPABASE_URL': 'https://auth.example.invalid',
            'NUVIO_SUPABASE_ANON_KEY': 'sb_publishable_test_fixture',
            'NUVIO_SUPABASE_FALLBACK_URL': '',
            'TV_LOGIN_WEB_BASE_URL': 'https://example.invalid/tv-login',
            'DEVICE_LOGIN_WEB_BASE_URL': 'https://example.invalid/link',
            'AVATAR_PUBLIC_BASE_URL': 'https://example.invalid/avatars',
            'TMDB_API_KEY': 'tmdb_test_fixture',
            'TRAKT_CLIENT_ID': 'trakt_test_fixture',
            'UNRELATED_CLIENT_SECRET': 'never_copy_this_fixture'
        }
        with tempfile.TemporaryDirectory() as tmp:
            ui=Path(tmp)/'ui';ui.mkdir()
            (ui/'index.html').write_text('<html><head></head><body></body></html>')
            (ui/'nuvio.env.js').write_text('var values = '+json.dumps(dict.fromkeys(official,''))+';')
            package=Path(tmp)/'official.zip'
            with zipfile.ZipFile(package,'w') as z:
                z.writestr('nuvio.env.js','var values = '+json.dumps(official)+';')
            with patch.object(build,'fetch',return_value=(None,package)):
                build.configure_ui(ui)
            configured=json.loads(re.search(r'var values = (\{.*?\});',(ui/'nuvio.env.js').read_text(),re.S)[1])
            for name,value in official.items():
                self.assertEqual(configured[name],'' if name=='UNRELATED_CLIENT_SECRET' else value,name)

    def test_ps5_index_paints_black_before_the_app_css(self):
        source=('<!doctype html>\n<html lang="en">\n  <head>\n'
                '    <link rel="stylesheet" href="css/bundle.css" />\n  </head>\n  <body></body>\n</html>\n')
        html=build.patch_index(source)
        self.assertLess(html.index('background-color:#000'),html.index('css/bundle.css'))
        self.assertEqual(html.count('ps5-input.js'),1)
        self.assertLess(html.index('ps5-input.js'),html.index('</head>'))

    def test_ps5_index_keeps_the_stylesheet_render_blocking(self):
        source=('<html>\n  <head>\n'
                '    <link rel="stylesheet" href="css/bundle.css" />\n  </head>\n'
                '  <body></body>\n</html>\n')
        html=build.patch_index(source)
        # The console's browser renders Nuvio unstyled when the sheet loads
        # through a media switch, so the plain blocking link must survive.
        self.assertIn('<link rel="stylesheet" href="css/bundle.css" />',html)
        self.assertNotIn('media="print"',html)

    def test_ps5_index_refuses_moved_or_repeated_anchors(self):
        with self.assertRaises(RuntimeError):
            build.patch_index('<html><body>no head</body></html>')
        with self.assertRaises(RuntimeError):
            build.patch_index('<head></head><script src="ps5-input.js"></script>')


class PlayerBackTests(unittest.TestCase):
    def test_nuvio_back_stops_session_native_back_retains_confirmation(self):
        import subprocess
        import shutil
        import polish
        compiler=shutil.which('clang++') or shutil.which('c++')
        if not compiler:self.skipTest('No host C++ compiler')
        fixed=polish.fix_player_back((APP.parent/'tests/fixtures/player_back.cpp.txt').read_text())
        body='\n'.join(l for l in fixed.splitlines() if not l.startswith('#include'))
        source=r"""
#include <cassert>
#include <cstdint>
namespace PadButtons { const uint32_t Circle=1; }
enum class ScreenId { ExitConfirm };
int nativeRequested=0;int evo_webui_native_requested(){return nativeRequested;}
struct Playback {int stopped=0;void stopPlayback(){stopped++;}} pb;
struct Screens {int returned=0,confirmed=0;void returnFromPlayback(){returned++;}void navigateTo(ScreenId){confirmed++;}} sm;
bool back(uint32_t pressed, Playback* playback, Screens* screenMgr) {
"""+body+r"""
return false;
}
int main(){
 assert(back(1,&pb,&sm));assert(pb.stopped==1 && sm.returned==1 && sm.confirmed==0);
 nativeRequested=1;assert(back(1,&pb,&sm));assert(pb.stopped==1 && sm.returned==1 && sm.confirmed==1);
 nativeRequested=0;assert(back(1,&pb,nullptr));assert(pb.stopped==2);
 assert(!back(0,&pb,&sm));assert(pb.stopped==2);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'back.cpp';p.write_text(source);binary=Path(tmp)/'back'
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',str(p),'-o',str(binary)],check=True,timeout=20)
            subprocess.run([str(binary)],check=True,timeout=10)


class UIServerTests(unittest.TestCase):
    """Exercise the console UI server's path, MIME and HTTP behavior on the host."""

    def test_path_confinement_mime_and_http_serve(self):
        import shutil
        import subprocess
        import time
        compiler=shutil.which('clang') or shutil.which('cc')
        if not compiler:
            self.skipTest('No host C compiler')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'webui'
            (root/'css').mkdir(parents=True)
            (root/'index.html').write_bytes(b'<html>NUVIO</html>')
            (root/'css'/'bundle.css').write_bytes(b'body{color:#000}')
            harness=Path(tmp)/'harness.c'
            harness.write_text('#include "'+str(APP/'ui_server.c')+'"\n'+r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    char out[4096];
    assert(nuvio_ui_path("/root","/",out,sizeof out)==0 && !strcmp(out,"/root/index.html"));
    assert(nuvio_ui_path("/root","/css/bundle.css",out,sizeof out)==0 && !strcmp(out,"/root/css/bundle.css"));
    assert(nuvio_ui_path("/root","/index.html?v=1",out,sizeof out)==0 && !strcmp(out,"/root/index.html"));
    assert(nuvio_ui_path("/root","/sub/",out,sizeof out)==0 && !strcmp(out,"/root/sub/index.html"));
    assert(nuvio_ui_path("/root","/a/./b",out,sizeof out)==0 && !strcmp(out,"/root/a/b"));
    assert(nuvio_ui_path("/root","/%2e%2e/secret",out,sizeof out)!=0);
    assert(nuvio_ui_path("/root","/a/../../secret",out,sizeof out)!=0);
    assert(nuvio_ui_path("/root","/a%00b",out,sizeof out)!=0);
    assert(strstr(nuvio_ui_mime("css/bundle.css"),"text/css")!=NULL);
    assert(strstr(nuvio_ui_mime("app.bundle.js"),"javascript")!=NULL);
    assert(!strcmp(nuvio_ui_mime("x.bin"),"application/octet-stream"));
    if (argc > 2) {
        if (nuvio_ui_server_open(argv[1], atoi(argv[2])) != 0) return 1;
        for (;;) nuvio_ui_server_poll(250);
    }
    return 0;
}
''')
            binary=Path(tmp)/'harness'
            subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-pthread',str(harness),'-o',str(binary)],check=True,timeout=20)
            subprocess.run([str(binary)],check=True,timeout=10)
            server=subprocess.Popen([str(binary),str(root),'45917'])
            try:
                base='http://127.0.0.1:45917'
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(base+'/css/bundle.css',timeout=0.5) as response:
                            self.assertEqual(response.read(),b'body{color:#000}')
                            self.assertEqual(response.headers['Content-Type'],'text/css; charset=utf-8')
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    self.fail('server did not answer')
                with urllib.request.urlopen(base+'/',timeout=1) as response:
                    self.assertEqual(response.read(),b'<html>NUVIO</html>')
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    urllib.request.urlopen(base+'/%2e%2e/secret',timeout=1)
                self.assertEqual(exc.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    urllib.request.urlopen(base+'/missing.js',timeout=1)
                self.assertEqual(exc.exception.code,404)
            finally:
                server.terminate()
                server.wait(timeout=5)


class PlaybackProfileReturnTests(unittest.TestCase):
    def test_restored_search_back_reaches_home_after_closing_actions(self):
        import polish
        import subprocess
        original='({consumeBackRequest() {\n      return this.closePosterOptionsMenu();\n}})'
        script=r'''
const vm=require('vm'),assert=require('assert');
for(const ps5 of [true,false])for(const stacked of [true,false]) {
 const context={__NUVIO_PS5__:ps5,Router:{stack:stacked?['detail']:[],current:'search',
 navigate(route){this.current=route;}}};vm.createContext(context);
 const screen=vm.runInContext(process.argv[1],context);
 screen.closePosterOptionsMenu=()=>true;
 assert.equal(screen.consumeBackRequest(),true);assert.equal(context.Router.current,'search');
 screen.closePosterOptionsMenu=()=>false;
 assert.equal(screen.consumeBackRequest(),ps5&&!stacked);
 assert.equal(context.Router.current,ps5&&!stacked?'home':'search');
}
'''
        subprocess.run(['node','-e',script,polish.patch_search_back(original)],check=True,timeout=10)

    def test_restored_detail_back_reaches_home_without_skipping_overlays_or_search(self):
        import polish
        import shutil
        import subprocess
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        source=(APP.parent/'tests/fixtures/detail_back.js.txt').read_text()
        script=r"""
const vm=require('vm'),assert=require('assert');
function boot(ps5,stack=[],params={}) {
 const ctx={__NUVIO_PS5__:ps5,Router:{current:'detail',stack,
  navigate(route){this.current=route;}}};
 vm.createContext(ctx);
 const screen=vm.runInContext(process.argv[1],ctx);screen.params=params;
 return {ctx,screen};
}
let {ctx,screen}=boot(true);
screen.heroPlayMenu={};screen.closeHeroMenus=()=>{screen.heroPlayMenu=null;};
assert.equal(screen.consumeBackRequest(),true);assert.equal(ctx.Router.current,'detail');
assert.equal(screen.heroPlayMenu,null); // First Back dismisses actions, not the page.
assert.equal(screen.consumeBackRequest(),true);assert.equal(ctx.Router.current,'home');
({ctx,screen}=boot(true,[],{returnToSearchOnBack:true}));
assert.equal(screen.consumeBackRequest(),true);assert.equal(ctx.Router.current,'search');
for(const [ps5,stack] of [[true,[{route:'folderDetail',params:{folderId:'fixture'}}]],[false,[]]]) {
 ({ctx,screen}=boot(ps5,stack));
 assert.equal(screen.consumeBackRequest(),false);assert.equal(ctx.Router.current,'detail');
}
({ctx,screen}=boot(false,[],{returnHomeOnBack:true}));
assert.equal(screen.consumeBackRequest(),true);assert.equal(ctx.Router.current,'home');
// Recreated Search has no Home predecessor. Returning from a result must
// consume the existing Search entry, not leave it behind as its own parent.
for(const parent of [[],[{route:'home',params:{}}]]) {
 ({ctx,screen}=boot(true,[...parent,{route:'search',params:{query:'Arrival'}}],{returnToSearchOnBack:true}));
 ctx.Router.popToExistingRoute=function(route) {
  if(this.stack.at(-1)?.route!==route)return false;
  this.stack.pop();this.current=route;return true;
 };
 assert.equal(screen.consumeBackRequest(),true);assert.equal(ctx.Router.current,'search');
 const search=vm.runInContext(process.argv[2],ctx);
 search.closePosterOptionsMenu=()=>false;
 if(!search.consumeBackRequest())ctx.Router.current=ctx.Router.stack.pop()?.route||'home';
 assert.equal(ctx.Router.current,'home');
}
"""
        search='({consumeBackRequest() {\n      return this.closePosterOptionsMenu();\n}})'
        subprocess.run([node,'-e',script,polish.patch_detail_back(source),
                        polish.patch_search_back(search)],check=True,timeout=10)
        with self.assertRaises(RuntimeError):
            polish.patch_detail_back('changed upstream')

    def test_browser_recreation_preserves_profile_and_route_once(self):
        import subprocess
        import shutil
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(process.argv[1],'utf8');
const decision=fs.readFileSync(process.argv[2],'utf8').replace(
 'if (hasSelectedProfileThisSession) {',
 'if (hasSelectedProfileThisSession || await canResumePs5Playback()) {');
const store=new Map();let active='2';
const profiles=[{id:'1'},{id:'2'}];store.set('profiles',profiles);
const boot=(search='',ps5=true)=>{
 const ctx={__NUVIO_PS5__:ps5,URLSearchParams,window:{location:{search}},
 LocalStore:{get:(k,d)=>store.has(k)?store.get(k):d,set:(k,v)=>store.set(k,v),remove:k=>store.delete(k)},
 ProfileManager:{getActiveProfileId:()=>active,getProfiles:async()=>profiles,
 isRememberLastProfileEnabled:()=>false,hasEverSelectedProfile:()=>true},
 ProfileSyncService:{pullProfileLockStates:async()=>({'2':true})},
 Router:{isWebOsResumeRouteRestorable:r=>['detail','stream','home','search'].includes(r)},console};
 vm.createContext(ctx);vm.runInContext('let hasSelectedProfileThisSession=false;'+code+decision,ctx);return ctx;
};
(async()=>{
 let ctx=boot();assert.equal((await ctx.shouldShowProfileSelection()).show,true);
 store.set('webos_last_resume_route',{route:'detail',params:{id:'movie'},savedAt:1});
 ctx.__nuvioSavePlaybackReturn();
 // Return after a two-hour movie, with remember-last-profile disabled and a PIN.
 store.get('ps5_playback_return').savedAt=Date.now()-2*60*60*1000;
 ctx=boot('?nuvioPlaybackReturn=1');
 assert.equal((await ctx.shouldShowProfileSelection()).show,false);
 assert.equal(store.get('webos_last_resume_route').params.id,'movie');
 assert(Date.now()-store.get('webos_last_resume_route').savedAt<1000);
 assert.equal(store.has('ps5_playback_return'),false);
 assert.equal((await boot().shouldShowProfileSelection()).show,true);
 // Native return restores browsing, not the one-shot playback intent. Keep
 // content/resume parameters and user settings while suppressing auto entry.
 for (const route of ['stream','detail','home']) {
   const params={itemId:'film-37',videoId:'episode-4',resumePositionMs:123000,
     manualSelection:false,continueWatchingBackHome:true,playOnLoad:true,autoOpenContinueWatching:true};
   store.set('webos_last_resume_route',{route,params,savedAt:1});
   ctx=boot();ctx.__nuvioSavePlaybackReturn();
   const snapshot=store.get('ps5_playback_return').resume;
   assert.equal(await boot('?nuvioPlaybackReturn=1').canResumePs5Playback(),true);
   const restored=store.get('webos_last_resume_route');
   assert.equal(restored.route,route);assert.equal(restored.params.itemId,'film-37');
   assert.equal(restored.params.videoId,'episode-4');assert.equal(restored.params.resumePositionMs,123000);
   assert.equal(restored.params.continueWatchingBackHome,true);
   if(route==='stream') assert.equal(restored.params.manualSelection,true);
   else if(route==='detail') {
     assert(!restored.params.playOnLoad);assert(!restored.params.autoOpenContinueWatching);
   } else assert.deepEqual(restored.params,params);
   assert.equal(snapshot.params.manualSelection,false);assert.equal(snapshot.params.playOnLoad,true);
 }
 // A cold title launch cannot reuse a leftover handoff snapshot.
 ctx.__nuvioSavePlaybackReturn();assert.equal((await boot().shouldShowProfileSelection()).show,true);
 // The diagnostic returns to the same selected profile and saved Search query.
 store.set('webos_last_resume_route',{route:'search',params:{query:'Amélie & 東京'},savedAt:1});
 ctx.__nuvioSavePlaybackReturn();
 const searchReturn=boot('?nuvioPlaybackReturn=1&nuvioImeComparisonReturn=1');
 assert.equal((await searchReturn.shouldShowProfileSelection()).show,false);
 assert.equal(store.get('webos_last_resume_route').route,'search');
 assert.equal(store.get('webos_last_resume_route').params.query,'Amélie & 東京');
 // A changed or deleted profile cannot inherit the previous selection.
 ctx.__nuvioSavePlaybackReturn();active='1';
 assert.equal(await boot('?nuvioPlaybackReturn=1').canResumePs5Playback(),false);
 active='2';ctx.__nuvioSavePlaybackReturn();profiles.pop();
 assert.equal(await boot('?nuvioPlaybackReturn=1').canResumePs5Playback(),false);
 profiles.push({id:'2'});ctx.__nuvioSavePlaybackReturn();
 store.get('ps5_playback_return').savedAt=Date.now()-25*60*60*1000;
 assert.equal(await boot('?nuvioPlaybackReturn=1').canResumePs5Playback(),false);
 ctx.__nuvioSavePlaybackReturn();
 assert.equal(await boot('?nuvioPlaybackReturn=1',false).canResumePs5Playback(),false);
 // Guest startup uses the same predicate, independently of remember-profile.
 ctx=boot();ctx.__nuvioSavePlaybackReturn();
 assert.equal(await boot('?nuvioPlaybackReturn=1').canResumePs5Playback(),true);
})().catch(e=>{console.error(e);process.exit(1)});
"""
        subprocess.run([node, '-e', script, str(APP/'ps5-resume.js'),
                        str(APP.parent/'tests/fixtures/app_profile_return.js.txt')],
                       check=True, timeout=10)

    def test_native_hook_saves_before_handoff_and_marks_only_nuvio_return(self):
        import json
        import polish
        import subprocess
        source = '''" function go(t){if(done)return;done=1;saveNow(1);"
"  fetch('/evo/play?url='+encodeURIComponent(abs)+'&title='+encodeURIComponent(t||'')+"
"   '&return='+encodeURIComponent(good));}"'''
        fixed = polish.fix_playback_handoff(source)
        # These C string literals also use JSON-compatible escaping. Decoding
        # them executes exactly the JavaScript emitted by the native hook.
        hook = ''.join(json.loads(line) for line in fixed.splitlines())
        script = r"""
const vm=require('vm'),assert=require('assert');
for(const nuvio of [true,false]){
 const order=[];let request;
 const ctx={NUVIO:nuvio,done:0,good:'http://127.0.0.1:8686/?existing=1#page',
 location:{href:'http://127.0.0.1:8686/'},abs:'https://fixture.invalid/video',
 window:{__nuvioSavePlaybackReturn:()=>{order.push('profile');return 'session-73';},__nuvioPlaybackStartSeconds:()=>371.664},URL,encodeURIComponent,
 saveNow:kind=>{assert.equal(kind,1);order.push('storage');},
 fetch:url=>{order.push('play');request=url}};
 vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);ctx.go('Title');
 const query=new URL(request,ctx.location.href).searchParams;
 const back=new URL(query.get('return'));
 assert.equal(query.get('start'),nuvio?'371.664':'0');
 assert.equal(query.get('session'),nuvio?'session-73':'');
 assert.equal(back.searchParams.get('nuvioPlaybackReturn'),nuvio?'1':null);
 assert.equal(back.searchParams.get('existing'),'1');assert.equal(back.hash,'#page');
 assert.deepEqual(order,nuvio?['profile','storage','play']:['storage','play']);
 ctx.go('again');assert.equal(order.length,nuvio?3:2);
}
// The live route points at player while history still describes stream.
const ctx={__NUVIO_PS5__:true,LocalStore:{get:()=>null,remove(){}},
 Router:{current:'player',currentParams:{}},history:{state:{route:'stream',params:{resumePositionMs:999000}}}};
vm.createContext(ctx);vm.runInContext(require('fs').readFileSync(process.argv[2],'utf8'),ctx);
for(const [params,expected] of [
 [{resumePositionMs:371664},371.664],
 [{resumePositionMs:371664,startFromBeginning:true},0],
 [{resumePositionMs:0,resumeProgressPercent:23,resumeDurationMs:7200000},1656],
 [{resumePositionMs:371664,resumeProgressPercent:23,resumeDurationMs:7200000},371.664],
 [{resumeProgressPercent:23},0],
 [{resumePositionMs:-100,resumeProgressPercent:Infinity,resumeDurationMs:7200000},0],
 [{resumePositionMs:Infinity},0],
 [{},0]
]){
 ctx.Router.currentParams=params;
 assert.equal(ctx.__nuvioPlaybackStartSeconds(),expected,JSON.stringify(params));
}
ctx.Router.currentParams={resumePositionMs:371664};ctx.Router.current='stream';
assert.equal(ctx.__nuvioPlaybackStartSeconds(),0);
ctx.Router.current='player';ctx.__NUVIO_PS5__=false;
assert.equal(ctx.__nuvioPlaybackStartSeconds(),0);
"""
        subprocess.run(['node', '-e', script, hook, str(APP/'ps5-resume.js')], check=True, timeout=10)
        with self.assertRaises(RuntimeError):
            polish.fix_playback_handoff('changed upstream')

    def test_native_progress_returns_to_its_profile_and_exact_episode(self):
        import subprocess
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const resume=fs.readFileSync(process.argv[1],'utf8');
const progress=fs.readFileSync(process.argv[2],'utf8');
const store=new Map([['profiles',[{id:'2'},{id:'7'}]]]),records=new Map();
let active='7',report={positionMs:2173500,durationMs:3600000},status=200;
const episode={itemId:'tt102938',itemType:'series',videoId:'tt102938:2:5',season:2,episode:5,
 title:'Series',episodeTitle:'Episode five',streamIdentity:{source:'selected-addon'}};
const boot=(search='?nuvioPlaybackReturn=1')=>{
 const ctx={__NUVIO_PS5__:true,URLSearchParams,AbortController,setTimeout,clearTimeout,encodeURIComponent,
 window:{location:{search}},console,
 LocalStore:{get:(k,d)=>store.has(k)?structuredClone(store.get(k)):d,
 set:(k,v)=>store.set(k,structuredClone(v)),remove:k=>store.delete(k)},
 ProfileManager:{getActiveProfileId:()=>active},
 Router:{current:'player',isWebOsResumeRouteRestorable:()=>false},
 PlayerController:{createProgressContext:()=>structuredClone(episode),
 flushProgress:async(positionMs,durationMs,clear,context)=>{
 records.set(`${active}:${context.itemId}:${context.season}:${context.episode}`,
 {...context,positionMs,durationMs});
 }},fetch:async url=>{
  assert.equal(new URL(url,'http://fixture.invalid').searchParams.get('session'),store.get('ps5_native_progress').session);
  return {status,ok:status===200,json:async()=>report};
 }};
 vm.createContext(ctx);vm.runInContext(resume+'\n'+progress,ctx);return ctx;
};
(async()=>{
 const ctx=boot();ctx.__nuvioSavePlaybackReturn();
 await boot().restorePs5PlaybackProgress();
 const saved=records.get('7:tt102938:2:5');
 assert.equal(saved.positionMs,2173500);assert.equal(saved.durationMs,3600000);
 assert.equal(saved.videoId,'tt102938:2:5');assert.equal(saved.episodeTitle,'Episode five');
 assert.equal(saved.streamIdentity.source,'selected-addon');assert.equal(records.size,1);
 assert(!store.has('ps5_native_progress'));
 // A later profile, cold launch, deleted profile or stale session must not inherit a report.
 for(const change of ['profile','cold','session','deleted','expired']){
  ctx.__nuvioSavePlaybackReturn();records.clear();
  if(change==='profile')active='2';
  if(change==='session')store.get('ps5_native_progress').session='previous-session';
  if(change==='deleted')store.set('profiles',[{id:'2'}]);
  if(change==='expired')store.get('ps5_playback_return').savedAt-=25*60*60*1000;
  await boot(change==='cold'?'':'?nuvioPlaybackReturn=1').restorePs5PlaybackProgress();
  assert.equal(records.size,0,change);active='7';store.set('profiles',[{id:'2'},{id:'7'}]);
 }
 // A profile change while the native response is in flight is also rejected.
 ctx.__nuvioSavePlaybackReturn();let pending=boot();
 pending.fetch=async()=>{active='2';return {status:200,ok:true,json:async()=>report}};
 await pending.restorePs5PlaybackProgress();assert.equal(records.size,0);active='7';
 // Failed starts and malformed timing cannot erase prior progress or mark watched.
 for(const value of [{positionMs:0,durationMs:3600000},{positionMs:NaN,durationMs:3600000},
                     {positionMs:300000,durationMs:-1}]){
  report=value;ctx.__nuvioSavePlaybackReturn();await boot().restorePs5PlaybackProgress();
  assert.equal(records.size,0);
 }
 status=204;ctx.__nuvioSavePlaybackReturn();await boot().restorePs5PlaybackProgress();
 assert.equal(records.size,0);assert(!store.has('ps5_native_progress'));
 assert(!store.has('ps5_playback_return'));
 // Failed transport keeps the return identity across browser recreation.
 status=503;ctx.__nuvioSavePlaybackReturn();await boot().restorePs5PlaybackProgress();
 assert(store.has('ps5_native_progress'));assert(store.has('ps5_playback_return'));
 status=200;report={positionMs:321987,durationMs:3600000};
 await boot().restorePs5PlaybackProgress();
 assert.equal(records.get('7:tt102938:2:5').positionMs,321987);
 assert(!store.has('ps5_playback_return'));records.clear();
 // A failed writer can retry in the same browser, without duplicate writes.
 ctx.__nuvioSavePlaybackReturn();pending=boot();
 const writer=pending.PlayerController.flushProgress;let attempts=0;
 pending.PlayerController.flushProgress=async(...args)=>{
  if(++attempts===1)throw new Error('temporary writer failure');
  return writer(...args);
 };
 await pending.restorePs5PlaybackProgress();assert.equal(records.size,0);
 assert(store.has('ps5_playback_return'));
 await pending.restorePs5PlaybackProgress();await pending.restorePs5PlaybackProgress();
 assert.equal(attempts,2);assert.equal(records.size,1);records.clear();
 // Re-entrant boot decisions share one import instead of overwriting a later update.
 status=200;report={positionMs:121234,durationMs:0};ctx.__nuvioSavePlaybackReturn();pending=boot();
 await pending.restorePs5PlaybackProgress();records.clear();await pending.restorePs5PlaybackProgress();
 assert.equal(records.size,0);
})().catch(e=>{console.error(e);process.exit(1)});
"""
        subprocess.run(['node', '-e', script, str(APP/'ps5-resume.js'),
                        str(APP/'ps5-playback-progress.js')], check=True, timeout=10)

    def test_native_progress_ignores_scrub_preview_before_stop(self):
        import polish
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'src').mkdir()
            (root/'include').mkdir()
            (root/'core/src/services').mkdir(parents=True)
            (root/'evo/services').mkdir(parents=True)
            (root/'evo/services/PlaybackController.hpp').write_text('')
            (root/'src/evo_webui.c').write_text('''
static char s_h_return[2048];
static void serve_evo(int fd, const char *path)
{
        s_h_start = seconds;
            s_play_start = s_h_start;
    *start = s_play_start;
    if (s_state != P_PLAYING) return;
}
''')
            (root/'include/evo_webui.h').write_text('''
void evo_webui_playback_ended(int played);
#if 0
static inline void evo_webui_playback_ended(int played) { (void)played; }
#endif
''')
            (root/'core/src/Application.cpp').write_text('''
void frame(PlaybackController *pb) {
            double pos = pb->getPositionSeconds();
}
''')
            (root/'core/src/services/PlaybackController.cpp').write_text('''#include "evo/services/PlaybackController.hpp"
void PlaybackController::stopPlayback() {
    if (isActive()) {
        saveResumePosition();
    }
}
''')
            polish.patch_playback_progress(root)
            # Execute the adapted frame and stop paths against the actual report
            # endpoint. A scrub-aware getter has the same preview semantics as EVO.
            bridge = (root/'src/evo_webui.c').read_text().split('static void serve_evo')[0]
            source = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <pthread.h>
using std::isfinite;
static pthread_mutex_t s_mx=PTHREAD_MUTEX_INITIALIZER;
static char body[256],status[32];
static int query_param(const char *,const char *,char *out,size_t cap) {
 snprintf(out,cap,"session-37");return 1;
}
static void respond(int,const char *s,const char *,const char *b,size_t n) {
 snprintf(status,sizeof status,"%s",s);memcpy(body,b,n);body[n]=0;
}
''' + bridge + r'''
class PlaybackController {
public:
 bool scrubbing=false;
 double position=890,target=950;
 bool isActive() const {return true;}
 bool isScrubbing() const {return scrubbing;}
 double getPositionSeconds() const {return scrubbing?target:position;}
 double getDurationSeconds() const {return 1000;}
 void saveResumePosition() {}
 void stopPlayback();
};
''' + (root/'core/src/Application.cpp').read_text() + '\n' + (
                root/'core/src/services/PlaybackController.cpp').read_text() + r'''
int main() {
 snprintf(s_progress_session,sizeof s_progress_session,"session-37");
 PlaybackController pb;
 frame(&pb);
 pb.scrubbing=true;
 frame(&pb); // Preview crosses 90%, but no seek has committed.
 pb.stopPlayback(); // Circle before the automatic scrub commit.
 s_progress_finished=1;
 playback_progress_serve(0,"/evo/progress?session=session-37");
 assert(!strcmp(status,"200 OK"));
 assert(!strcmp(body,"{\"positionMs\":890000,\"durationMs\":1000000}"));
 // A real later position, including a completed seek, must still save on stop.
 s_progress_finished=0;pb.scrubbing=false;pb.position=920;
 pb.stopPlayback();s_progress_finished=1;
 playback_progress_serve(0,"/evo/progress?session=session-37");
 assert(!strcmp(body,"{\"positionMs\":920000,\"durationMs\":1000000}"));
 // A committed seek to zero must not report the stale near-end sample.
 s_progress_finished=0;pb.position=0;pb.stopPlayback();s_progress_finished=1;
 playback_progress_serve(0,"/evo/progress?session=session-37");
 assert(!strcmp(status,"204 No Content"));
 // Teardown's zero duration must not erase an otherwise valid position.
 s_progress_finished=0;pb.position=450;frame(&pb);
 evo_webui_progress_sample(0,0);s_progress_finished=1;
 playback_progress_serve(0,"/evo/progress?session=session-37");
 assert(!strcmp(body,"{\"positionMs\":450000,\"durationMs\":1000000}"));
}
'''
            probe = root/'progress.cpp'
            probe.write_text(source)
            binary = root/'progress'
            subprocess.run(['c++', '-std=c++17', '-pthread', '-I'+str(root),
                            '-I'+str(root/'include'), str(probe), '-o', str(binary)],
                           check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)
