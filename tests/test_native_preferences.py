"""Execute pinned frontend helpers, the real DTO/cache/decoder, and selectors.

Offline host tests are not evidence of PS5 decoder/output or owner addon data.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts import native_preferences, native_subtitles, subtitle_handoff
from tests.test_native_subtitles import compile_run, source_file
from tests.test_subtitle_handoff import frontend_file

ROOT = Path(__file__).resolve().parents[1]
PLAYER = 'js/ui/screens/player/'


def export(source, name):
    match = re.search(r'export (?:function|const) ' + name + r'\b', source)
    if not match:
        raise AssertionError(name)
    return source[match.start():].split('\nexport ', 1)[0].replace('export ', '', 1)


def frontend_dtos(directory):
    helpers = ''
    for filename, names in (
        ('02-language-code-aliases', ('LANGUAGE_CODE_ALIASES', 'LANGUAGE_NAME_ALIASES',
                                     'SUBTITLE_LANGUAGE_OFF_KEY', 'SUBTITLE_LANGUAGE_UNKNOWN_KEY', 'cleanDisplayText')),
        ('03-normalize-web-os-html-subtitle-text', ('normalizeComparableText',)),
        ('05-normalize-track-language-code', ('normalizeTrackLanguageCode', 'normalizeLanguageNameText',
                                             'inferTrackLanguageCodeFromText')),
        ('06-get-track-flag-candidates', ('isForcedAddonSubtitle',)),
        ('09-format-bytes', ('normalizeSubtitleLanguageKey', 'extractSubtitleLanguageSetting')),
    ):
        source = frontend_file(PLAYER + 'playerScreenHelpers-' + filename + '.js')
        helpers += '\n'.join(export(source, name) for name in names) + '\n'
    helpers += 'const normalizeSubtitleLanguageAlias = (() => {\n' + frontend_file(
        'js/core/player/subtitleLanguageAliases.js').replace('export ', '') + \
        '\nreturn normalizeSubtitleLanguageAlias;})();\n'
    # Execute the actual methods objects (not mock preference helpers).
    for filename in ('50-scroll-subtitle-rail-node-into-view',
                     '51-get-startup-preferred-subtitle-language-targets'):
        helpers += frontend_file(PLAYER + 'playerScreenMethods-' + filename + '.js').replace(
            'import * as internals from "./playerScreenContext.js";', '').replace('export function', 'function')
    source = native_preferences.patch_frontend_source((ROOT / 'scripts/ps5-subtitles.js').read_text())
    data = Path(directory) / 'frontend.json'
    data.write_text(json.dumps({'helpers': helpers, 'bridge': source,
                               'general': (ROOT / 'scripts/ps5-general.js').read_text().split('// Preference identities')[0]}))
    harness = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
 const input=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
 let settings={},profile='one',sent,finish;
 const screen={contentLanguage:'ja',playerMountToken:1,activePlaybackUrl:'https://media.invalid/fixture',
   subtitles:[],loadSubtitles:()=>Promise.resolve(),getCurrentStreamCandidate:()=>({id:'one'}),
   collectSubtitleOptionItems(){return this.subtitles.map(track=>({sourceType:'addon',entry:{track},
     isForced:ctx.isForcedAddonSubtitle(track)}));}};
 const router={current:'player',currentParams:{itemId:'fixture'},getCurrentScreen:()=>screen};
 const ctx=vm.createContext({URL,AbortController,setTimeout,clearTimeout,__NUVIO_PS5__:true,
   Router:router,ProfileManager:{getActiveProfileId:()=>profile},
   PlayerSettingsStore:{get:()=>settings},I18n:{getLocale:()=> 'hu-HU'},
   async fetch(url,options){assert.equal(url,'/evo/subtitles');sent=JSON.parse(options.body);return {ok:true};}});
 vm.runInContext(input.helpers+`
 const internals={PlayerSettingsStore,I18n,SUBTITLE_LANGUAGE_OFF_KEY,cleanDisplayText,
   normalizeComparableText,normalizeTrackLanguageCode,normalizeSubtitleLanguageKey,extractSubtitleLanguageSetting};
 Object.assign(globalThis,{isForcedAddonSubtitle});
 globalThis.methods={...createPlayerScreenMethods50(),...createPlayerScreenMethods51()};`,ctx);
 Object.assign(screen,ctx.methods);
 vm.runInContext(input.general+input.bridge,ctx);
 const output={};
 async function capture(name,audio,subtitle,extra={}){
   settings={subtitlesEnabled:true,preferredAudioLanguage:audio,secondaryPreferredAudioLanguage:'en',
     subtitleLanguage:subtitle,secondarySubtitleLanguage:'en',...extra};
   assert.equal(await ctx.__nuvioPrepareSubtitles(),true);
   assert.equal(await ctx.__nuvioSendSubtitles('one'),true);output[name]=sent;
   return sent.preferences;
 }
 assert.deepEqual(await capture('primary','es','es'),{mode:'language',audio:['es','en'],subtitle:['es','en']});
 assert.deepEqual(await capture('secondary','zz','zz'),{mode:'language',audio:['zz','en'],subtitle:['zz','en']});
 assert.deepEqual((await capture('system','system','system')).audio,['hu-hu','en']);
 assert.deepEqual(output.system.preferences.subtitle,['hu-hu','en']);
 assert.deepEqual((await capture('original','original','es')).audio,['ja','en']);
 screen.contentLanguage='';assert.deepEqual((await capture('originalMissing','original','es')).audio,['hu-hu','en']);
 assert.deepEqual((await capture('none','default','off',{secondaryPreferredAudioLanguage:'device'})).audio,[]);
 assert.deepEqual(output.none.preferences.subtitle,[]);assert.equal(output.none.preferences.mode,'off');
 await capture('absent','zz','zz',{secondaryPreferredAudioLanguage:'none',secondarySubtitleLanguage:'off'});
 await capture('unresolved','es','not a language',{useForcedSubtitles:true});
 assert.deepEqual(output.unresolved.preferences.subtitle,['','en']);
 await capture('disabled','es','es',{subtitlesEnabled:false});assert.equal(output.disabled.preferences.mode,'off');
 await capture('forced','es','es',{useForcedSubtitles:true});assert.equal(output.forced.preferences.mode,'audio-forced');
 await capture('forcedOnly','es','forced');assert.deepEqual(output.forcedOnly.preferences.subtitle,[]);
 await capture('regionForced','pt-br','pt-br',{useForcedSubtitles:true});
 // Actual frontend forced resolver: audio is unknown until native demux.
 screen.collectAudioOptionItems=()=>[{selected:true,languageKey:'pt-pt'}];
 assert.equal(screen.getStartupForcedSubtitleLanguageTarget(),null);
 screen.collectAudioOptionItems=()=>[{selected:true,languageKey:'pt'}];
 assert.equal(screen.getStartupForcedSubtitleLanguageTarget(),'pt-br');
 // Only candidates the existing sender accepts; forced uses real helper.
 screen.subtitles=[{url:'https://subs.invalid/forced.vtt',lang:'es',addonName:'Fixture'},
   {url:'https://subs.invalid/plain',lang:'es',addonName:'Fixture'},
   {url:'https://subs.invalid/secret',lang:'es',headers:{Authorization:'fixture'}}];
 await capture('addons','es','es');assert.deepEqual(sent.subtitles.map(x=>x.forced),[true,false]);
 await capture('forcedAddons','es','es',{useForcedSubtitles:true});
 // Profile/remount/source changes cancel; settings freeze when prepare settles.
 // No profile identifiers are transported.
 profile='two';assert.equal(await ctx.__nuvioSendSubtitles('one'),false);profile='one';
 settings.subtitleLanguage='de';assert.equal(await ctx.__nuvioSendSubtitles('one'),false);
 profile=null;assert.equal(await ctx.__nuvioPrepareSubtitles(),true);
 assert.equal(await ctx.__nuvioSendSubtitles('one'),true);assert(!('preferences' in sent));profile='one';
 screen.loadSubtitles=()=>new Promise(resolve=>{finish=resolve;});
 settings.preferredAudioLanguage='original';screen.contentLanguage='';
 const metadata=ctx.__nuvioPrepareSubtitles();screen.contentLanguage='ja';finish();
 assert.equal(await metadata,true);assert.equal(await ctx.__nuvioSendSubtitles('one'),true);
 assert.equal(sent.preferences.audio[0],'ja'); // not premature system fallback or aborted startup
 const pending=ctx.__nuvioPrepareSubtitles();screen.playerMountToken++;finish();assert.equal(await pending,null);
 screen.loadSubtitles=()=>Promise.resolve();await ctx.__nuvioPrepareSubtitles();
 screen.activePlaybackUrl='https://media.invalid/other';assert.equal(await ctx.__nuvioSendSubtitles('one'),false);
 await ctx.__nuvioPrepareSubtitles();router.currentParams.itemId='other';assert.equal(await ctx.__nuvioSendSubtitles('one'),false);
 router.current='home';assert.equal(await ctx.__nuvioPrepareSubtitles(),null);
 assert(!JSON.stringify(output.primary).includes('profile'));
 process.stdout.write(JSON.stringify(output));
})().catch(error=>{console.error(error);process.exit(1);});
'''
    result = subprocess.run(['node', '-e', harness, str(data)], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


class NativePreferenceTests(unittest.TestCase):
    def test_adapter_validates_all_sources_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            fixtures = {
                'Makefile': source_file('Makefile'),
                'src/evo_webui.c': (ROOT / 'scripts/ps5-subtitles.c').read_text(),
                'media/src/evo_subtitle.c': native_subtitles.patch_subtitle_source(
                    source_file('media/src/evo_subtitle.c')),
                'core/src/services/PlaybackController.cpp': subtitle_handoff.patch_controller_source(
                    native_subtitles.patch_controller_source(source_file('core/src/services/PlaybackController.cpp'))),
            }
            (app / 'include').mkdir()
            for name, text in fixtures.items():
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            controller = app / 'core/src/services/PlaybackController.cpp'
            controller.write_text(controller.read_text().replace('    // Subtitle setup\n', '    // drift\n'))
            before = {p.relative_to(app): p.read_bytes() for p in app.rglob('*') if p.is_file()}
            with self.assertRaises(RuntimeError):
                native_preferences.patch_native(app)
            self.assertEqual(before, {p.relative_to(app): p.read_bytes() for p in app.rglob('*') if p.is_file()})
            controller.write_text(fixtures['core/src/services/PlaybackController.cpp'])
            native_preferences.patch_native(app)
            self.assertIn('    src/ps5-preferences.c \\\n', (app / 'Makefile').read_text())
            before = {p.relative_to(app): p.read_bytes() for p in app.rglob('*') if p.is_file()}
            with self.assertRaises(RuntimeError):
                native_preferences.patch_native(app)
            self.assertEqual(before, {p.relative_to(app): p.read_bytes() for p in app.rglob('*') if p.is_file()})

    def test_real_frontend_helpers_and_session_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            frontend_dtos(tmp)

    def test_native_dto_selectors_cues_manual_reopens_and_isolation(self):
        if not shutil.which('pkg-config'):
            self.skipTest('FFmpeg development libraries unavailable')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'libavformat', 'libavcodec', 'libavutil'],
                               capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('FFmpeg development libraries unavailable')
        subtitle = native_preferences.patch_subtitle_source(native_subtitles.patch_subtitle_source(
            source_file('media/src/evo_subtitle.c')))
        web = native_preferences.patch_web_source((ROOT / 'scripts/ps5-subtitles.c').read_text())
        # HTTP framing is already covered by the handoff suite. This probe uses
        # the real decoder, matched-session promotion and import/clear routine.
        web = web.split('static void serve_subtitles(', 1)[0] + 'static void subtitles_handoff(' + web.split(
            'static void subtitles_handoff(', 1)[1]
        controller = native_preferences.patch_controller_source(subtitle_handoff.patch_controller_source(
            native_subtitles.patch_controller_source(source_file('core/src/services/PlaybackController.cpp'))))
        selection = controller.split('    if (!profilePolicy && chosen_program < 0 && evo_langpref_audio()[0]) {', 1)[1]
        selection = '    if (!profilePolicy && chosen_program < 0 && evo_langpref_audio()[0]) {' + selection.split(
            '    m_requestedAudioStream = -1;', 1)[0]
        gate = '    const bool profilePolicy = ' + controller.split('    const bool profilePolicy = ', 1)[1].split(
            '    stopPlayback();', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dtos = directory / 'dtos.json'
            dtos.write_text(json.dumps(frontend_dtos(tmp)))
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
            cpp = directory / 'controller.cpp'
            cpp.write_text('''
#include <cstring>
#include <string>
#include "ps5-preferences.h"
#include "evo_langpref.h"
#define evo_bt(...) ((void)0)
#define EVO_LOGW(...) ((void)0)
extern "C" int controller_audio(AVFormatContext *play_fmt, bool profilePolicy,
 int audio_stream_index, int chosen_program, nuvio_preferences_snapshot profileReopen, int m_requestedAudioStream) {
''' + selection + '''
return audio_stream_index;
}
extern "C" int controller_reopen(const char *provider, const char *key, const char *url,
 const char *oldProvider, const char *oldKey, const char *oldUrl, bool playing) {
 struct Source {std::string provider,item_id,url;};
 Source source{provider,key,url},m_source{oldProvider,oldKey,oldUrl};
 std::string rawUrl=url,m_currentFilePath=playing ? oldUrl : "";
 int audio_stream_index=0;
''' + gate + '\nreturn profileReopen.valid;\n}\n')
            obj = directory / 'controller.o'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', tmp,
                            '-c', str(cpp), '-o', str(obj)], check=True, timeout=30)
            source = NATIVE_PRELUDE + subtitle + source_file('media/src/evo_langpref.c') + \
                subtitle_handoff.patch_online_source(source_file('addons/src/evo_online_subs.c')) + \
                web + NATIVE_MAIN
            result = compile_run(source, tmp, [dtos, directory], extra_flags=[
                '-D_DEFAULT_SOURCE', '-I', tmp, '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                str(directory / 'cJSON.c'), str(directory / 'preferences.c'), str(obj),
                '-lstdc++', '-pthread', *flags.stdout.split()])
            self.assertIn('preferences: real DTO/cache/decoder cues and manual reopens OK', result)


NATIVE_PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include "ps5-preferences.h"
#include "evo_ntfs.h"
#include "evo_charset.h"
#include "evo_net.h"
AVFormatContext *play_fmt;
int player_paused=1,audio_stream_index=-1;
double resume_base_offset_seconds;
long long controls_last_used_ms;
static const char *test_directory;
long long now_ms(void){return 1;}
void toast(const char *a,const char *b){(void)a;(void)b;}
void evo_subsync_cancel(void){}
void evo_boot_log(const char *format,...){(void)format;}
int evo_ntfs_is_url(const char *p){(void)p;return 0;}
int evo_ntfs_read_file(const char *p,unsigned char **out,size_t *n,size_t cap){(void)p;(void)out;(void)n;(void)cap;return -1;}
char *evo_charset_to_utf8(const unsigned char *s,size_t n,const char *p,const char **name){
 (void)p;*name="UTF-8";char *out=malloc(n+1);assert(out);memcpy(out,s,n);out[n]=0;return out;
}
const char *evo_data_path(const char *name){static char p[1024];snprintf(p,sizeof p,"%s/%s",test_directory,name);return p;}
const char *evo_language_native_name(const char *s){return s;}
int evo_net_http_get_sync(const char *url,const char **h,int hn,char **out,size_t *n,int *status){
 (void)h;(void)hn;const char *body=strstr(url,"forced") ?
 "WEBVTT\n\n00:05.000 --> 00:09.000\nForced addon\n\n" :
 "1\n00:00:05,000 --> 00:00:09,000\nNormal addon\n\n";
 *out=strdup(body);*n=strlen(body);*status=200;return 0;
}
double evo_pb_position_s(void){return 6;}
int prospero_request_inplace_seek(double seconds,int paused){(void)seconds;(void)paused;return 1;}
static pthread_mutex_t s_mx=PTHREAD_MUTEX_INITIALIZER;
extern int controller_audio(AVFormatContext *,bool,int,int,nuvio_preferences_snapshot,int);
extern int controller_reopen(const char *,const char *,const char *,const char *,const char *,const char *,bool);
'''

NATIVE_MAIN = r'''
static cJSON *dtos;
static void import_case(const char *name,const char *session){
 char *body=cJSON_PrintUnformatted(cJSON_GetObjectItemCaseSensitive(dtos,name));assert(body);
 assert(subtitles_decode(body,strlen(body)));free(body);subtitles_handoff(session);
 s_play_subtitles=s_h_subtitles;char key[80];evo_webui_import_subtitles(key,sizeof key);
 assert(!s_play_subtitles.preferences.valid); /* Import really clears the DTO. */
}
static AVStream *add_stream(enum AVMediaType type,enum AVCodecID codec,const char *lang,int disposition){
 AVStream *st=avformat_new_stream(play_fmt,NULL);assert(st);st->codecpar->codec_type=type;
 st->codecpar->codec_id=codec;st->time_base=(AVRational){1,1000};st->disposition=disposition;
 av_dict_set(&st->metadata,"language",lang,0);return st;
}
static void cue(const char *expected){
 AVPacket *p=av_packet_alloc();assert(p);assert(av_new_packet(p,(int)strlen(expected))==0);
 memcpy(p->data,expected,strlen(expected));p->stream_index=prospero_embedded_subtitle_stream_index;
 p->pts=5000;p->duration=4000;prospero_embedded_subtitle_decode_packet(p);av_packet_free(&p);
 char text[768];assert(prospero_embedded_subtitle_text_at(6,text,sizeof text));assert(!strcmp(text,expected));
}
static void addon_cue(const char *expected){
 const ProsperoSubtitleCue *c=prospero_subtitle_active_cue(6);assert(c && !strcmp(c->text,expected));
 assert(prospero_subtitle_use_external && prospero_subtitle_enabled);
}
int main(int argc,char **argv){
 assert(argc==3);test_directory=argv[2];FILE *f=fopen(argv[1],"rb");assert(f);
 assert(!fseek(f,0,SEEK_END));long n=ftell(f);rewind(f);char *body=malloc((size_t)n+1);assert(body);
 assert(fread(body,1,(size_t)n,f)==(size_t)n);body[n]=0;fclose(f);dtos=cJSON_Parse(body);free(body);assert(dtos);
 play_fmt=avformat_alloc_context();assert(play_fmt);
 add_stream(AVMEDIA_TYPE_AUDIO,AV_CODEC_ID_AAC,"eng",AV_DISPOSITION_DEFAULT); // 0
 add_stream(AVMEDIA_TYPE_AUDIO,AV_CODEC_ID_AAC,"spa",AV_DISPOSITION_DEFAULT|AV_DISPOSITION_COMMENT); // 1
 add_stream(AVMEDIA_TYPE_AUDIO,AV_CODEC_ID_AAC,"es",0); // 2
 add_stream(AVMEDIA_TYPE_AUDIO,AV_CODEC_ID_NONE,"zz",0); // 3 unsupported
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"spa",AV_DISPOSITION_DEFAULT); // 4
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"spa",AV_DISPOSITION_COMMENT); // 5
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"eng",0); // 6
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"spa",AV_DISPOSITION_FORCED); // 7
 add_stream(AVMEDIA_TYPE_AUDIO,AV_CODEC_ID_AAC,"pt-pt",0); // 8
 add_stream(AVMEDIA_TYPE_AUDIO,AV_CODEC_ID_AAC,"pt",0); // 9
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"pt-br",AV_DISPOSITION_FORCED); // 10
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"pt-pt",AV_DISPOSITION_FORCED); // 11
 add_stream(AVMEDIA_TYPE_SUBTITLE,AV_CODEC_ID_SUBRIP,"pt-br",0); // 12
 nuvio_preferences_snapshot fresh={0},reopen={0};
 import_case("primary","wrong");assert(!nuvio_preferences_active("web","web:one"));
 import_case("primary","one");assert(nuvio_preferences_active("web","web:one"));
 assert(!nuvio_preferences_active("","web:one") && !nuvio_preferences_active("web","web:two"));
 assert(controller_reopen("web","web:one","file-one","web","web:one","file-one",true));
 assert(!controller_reopen("web","web:one","file-two","web","web:one","file-one",true));
 assert(!controller_reopen("web","web:two","file-one","web","web:one","file-one",true));
 assert(!controller_reopen("","web:one","file-one","web","web:one","file-one",true));
 assert(!controller_reopen("web","web:one","file-one","web","web:one","file-one",false));
 evo_langpref_set_audio("eng");evo_langpref_set_subtitle("ita");
 assert(controller_audio(play_fmt,true,0,-1,fresh,-1)==2); // not default commentary
 assert(controller_audio(play_fmt,true,0,-1,fresh,0)==0); // manual request wins
 AVProgram *program=av_new_program(play_fmt,1);assert(program);av_program_add_stream_index(play_fmt,1,0);
 assert(controller_audio(play_fmt,true,0,0,fresh,-1)==0); // retain HLS program pairing
 assert(controller_audio(play_fmt,false,2,-1,fresh,-1)==0); // native preference unchanged
 assert(!strcmp(evo_langpref_audio(),"eng") && !strcmp(evo_langpref_subtitle(),"ita"));
 prospero_secondary_subtitle_requested=6; // prior session, never an embedded-index contract
 nuvio_preferences_subtitles(play_fmt,2,&fresh);assert(prospero_embedded_subtitle_stream_index==4);cue("Primary Spanish");
 assert(prospero_secondary_subtitle_requested==PROSPERO_SECONDARY_NONE);
 assert(player_paused==1); // No seek/pause mutation in startup selectors.
 // Manual embedded/off survives same-source reopen and cannot restore addon.
 assert(prospero_subtitle_select_primary(6));cue("Manual English");prospero_subtitle_enabled=0;
 nuvio_preferences_capture(&reopen,0);assert(controller_audio(play_fmt,true,2,-1,reopen,-1)==0);
 nuvio_preferences_subtitles(play_fmt,0,&reopen);assert(!prospero_subtitle_enabled);
 assert(prospero_embedded_subtitle_stream_index==6);cue("Still manual English");
 import_case("secondary","one");assert(controller_audio(play_fmt,true,2,-1,fresh,-1)==0);
 nuvio_preferences_subtitles(play_fmt,0,&fresh);assert(prospero_embedded_subtitle_stream_index==6);cue("Secondary English");
 import_case("none","one");assert(controller_audio(play_fmt,true,2,-1,fresh,-1)==2);
 nuvio_preferences_subtitles(play_fmt,2,&fresh);assert(!prospero_subtitle_enabled);
 import_case("absent","one");assert(controller_audio(play_fmt,true,2,-1,fresh,-1)==2);
 nuvio_preferences_subtitles(play_fmt,2,&fresh);assert(!prospero_subtitle_enabled); // no unrelated English
 import_case("unresolved","one");nuvio_preferences_subtitles(play_fmt,0,&fresh);
 assert(prospero_embedded_subtitle_stream_index==6);cue("Secondary normal, not forced");
 import_case("disabled","one");nuvio_preferences_subtitles(play_fmt,2,&fresh);assert(!prospero_subtitle_enabled);
 import_case("forced","one");nuvio_preferences_subtitles(play_fmt,2,&fresh);
 assert(prospero_embedded_subtitle_stream_index==7);cue("Forced Spanish");
 nuvio_preferences_subtitles(play_fmt,0,&fresh);assert(prospero_embedded_subtitle_stream_index==4);cue("Foreign audio normal Spanish");
 import_case("forcedOnly","one");nuvio_preferences_subtitles(play_fmt,2,&fresh);
 assert(prospero_embedded_subtitle_stream_index==7);cue("Forced-only Spanish");
 import_case("regionForced","one");nuvio_preferences_subtitles(play_fmt,8,&fresh);
 assert(prospero_embedded_subtitle_stream_index==12);cue("Sibling region needs normal subtitles");
 nuvio_preferences_subtitles(play_fmt,9,&fresh);assert(prospero_embedded_subtitle_stream_index==10);
 cue("Plain base audio accepts requested forced region");
 // Normal subtitle policy must not silently take a forced embedded track.
 import_case("addons","one");play_fmt->streams[4]->codecpar->codec_id=AV_CODEC_ID_DVD_SUBTITLE;
 play_fmt->streams[5]->codecpar->codec_id=AV_CODEC_ID_NONE;
 nuvio_preferences_subtitles(play_fmt,2,&fresh);addon_cue("Normal addon");assert(evo_osubs_active()==1);
 // Real external path survives clear/import-free audio reopen, including OFF.
 // A failed later download may overwrite scratch while loaded cues stay good.
 FILE *scratch=fopen(prospero_subtitle_path,"wb");assert(scratch);
 assert(fputs("unsupported subtitle body",scratch)>=0);assert(!fclose(scratch));
 prospero_subtitle_enabled=0;nuvio_preferences_capture(&reopen,0);
 nuvio_preferences_subtitles(play_fmt,0,&reopen);assert(!prospero_subtitle_enabled);
 assert(prospero_subtitle_use_external);assert(prospero_subtitle_active_cue(6));
 // Explicit embedded after online remains embedded on reopen.
 assert(prospero_subtitle_select_primary(6));nuvio_preferences_capture(&reopen,0);
 nuvio_preferences_subtitles(play_fmt,0,&reopen);assert(!prospero_subtitle_use_external);
 assert(prospero_embedded_subtitle_stream_index==6);cue("Embedded after addon");
 import_case("forcedAddons","one");play_fmt->streams[7]->codecpar->codec_id=AV_CODEC_ID_NONE;
 nuvio_preferences_subtitles(play_fmt,2,&fresh);addon_cue("Forced addon");assert(evo_osubs_active()==0);
 // A registered decoder can still fail to open. Fall back through real cache,
 // downloader/file writer and parser, not a pretend supported URL extension.
 import_case("addons","one");play_fmt->streams[4]->codecpar->codec_id=AV_CODEC_ID_MOV_TEXT;
 play_fmt->streams[4]->codecpar->width=play_fmt->streams[4]->codecpar->height=-1;
 nuvio_preferences_subtitles(play_fmt,2,&fresh);addon_cue("Normal addon");
 play_fmt->streams[5]->codecpar->codec_id=AV_CODEC_ID_SUBRIP;
 nuvio_preferences_subtitles(play_fmt,2,&fresh);assert(prospero_embedded_subtitle_stream_index==5);
 cue("Next embedded decoder works");
 // Reject DTO duplicates instead of shifting forced flags when cache deduplicates.
 body=cJSON_PrintUnformatted(cJSON_GetObjectItemCaseSensitive(dtos,"addons"));assert(body);
 cJSON *duplicate=cJSON_Parse(body);free(body);assert(duplicate);
 cJSON *entries=cJSON_GetObjectItemCaseSensitive(duplicate,"subtitles");
 const char *first=cJSON_GetObjectItemCaseSensitive(cJSON_GetArrayItem(entries,0),"url")->valuestring;
 cJSON_DeleteItemFromObject(cJSON_GetArrayItem(entries,1),"url");
 assert(cJSON_AddStringToObject(cJSON_GetArrayItem(entries,1),"url",first));
 body=cJSON_PrintUnformatted(duplicate);assert(!subtitles_decode(body,strlen(body)));free(body);cJSON_Delete(duplicate);
 // Next session (including absent/old sender policy) cannot inherit profile.
 const char *old="{\"session\":\"two\",\"subtitles\":[]}";
 assert(subtitles_decode(old,strlen(old)));subtitles_handoff("two");s_play_subtitles=s_h_subtitles;
 char key[80];evo_webui_import_subtitles(key,sizeof key);assert(!nuvio_preferences_active("web","web:one"));
 assert(!nuvio_preferences_active("web","web:two"));
 nuvio_preferences_t bad; cJSON *invalid=cJSON_Parse("{\"mode\":\"language\",\"audio\":[\"https://private\"],\"subtitle\":[]}");
 assert(!nuvio_preferences_decode(invalid,&bad));cJSON_Delete(invalid);
 prospero_embedded_subtitle_close();avformat_free_context(play_fmt);cJSON_Delete(dtos);
 puts("preferences: real DTO/cache/decoder cues and manual reopens OK");return 0;
}
'''


if __name__ == '__main__':
    unittest.main()
