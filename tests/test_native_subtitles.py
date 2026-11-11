"""Execute the actual external loader/controller regions, without network/PS5.

Use NUVIO_SUBTITLES_APP to check a fully adapted, unmodified generated app.
Otherwise read the verified, locally cached pinned archive. Never download it.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_subtitles


def source_file(relative):
    app = os.environ.get('NUVIO_SUBTITLES_APP')
    if app:
        return (Path(app) / relative).read_text()
    pin = next(p for p in json.loads((ROOT / 'deps.lock').read_text())['artifacts']
               if p['id'] == 'evo-player-nuvio-source')
    archive = Path(os.environ.get('NUVIO_CACHE_DIR', ROOT / '.cache')) / pin['cache_file']
    if not archive.exists():
        raise unittest.SkipTest('Pinned EVO archive not cached; no network fetch')
    with archive.open('rb') as handle:
        if hashlib.file_digest(handle, 'sha256').hexdigest() != pin['sha256']:
            raise RuntimeError('Cached EVO archive checksum mismatch')
    with tarfile.open(archive) as handle:
        member = pin['directory'] + '/projects/evoplayer/' + relative
        return handle.extractfile(member).read().decode()


def region(source, start, end):
    return start + source.split(start, 1)[1].split(end, 1)[0]


def compile_run(source, directory, arguments=(), cpp=False, extra_flags=()):
    # Host probes need the host sanitizer runtime, not the PS5 build's LLVM.
    compiler = shutil.which('c++' if cpp else 'cc') or shutil.which('clang++' if cpp else 'clang')
    if not compiler:
        raise unittest.SkipTest('No host compiler')
    path = Path(directory) / ('probe.cpp' if cpp else 'probe.c')
    binary = Path(directory) / 'probe'
    path.write_text(source)
    subprocess.run([compiler, '-std=c++17' if cpp else '-std=c11',
                    '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', str(path), '-o', str(binary), *extra_flags],
                   check=True, timeout=30)
    result = subprocess.run([str(binary), *map(str, arguments)],
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


LOADER_STUBS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PROSPERO_SUBTITLE_MAX_CUES 2048
#define PROSPERO_SUBTITLE_TEXT_SIZE 512
typedef struct { double start_seconds, end_seconds; char text[512]; } ProsperoSubtitleCue;
static ProsperoSubtitleCue prospero_subtitle_cues[2048];
static int prospero_subtitle_count;
static char prospero_subtitle_path[512];
static int evo_ntfs_is_url(const char *p) { (void)p; return 0; }
static int evo_ntfs_read_file(const char *p, unsigned char **out, size_t *len, size_t cap) {
    (void)p; (void)out; (void)len; (void)cap; return -1;
}
static char *evo_charset_to_utf8(const unsigned char *raw, size_t len, const char *path, const char **name) {
    (void)path; *name="UTF-8"; char *s=malloc(len+1); if(s){memcpy(s,raw,len);s[len]=0;} return s;
}
static void evo_boot_log(const char *fmt, ...) { (void)fmt; }
'''


class NativeSubtitleTests(unittest.TestCase):
    def test_real_embedded_switch_refills_presentation_cues(self):
        """One real Matroska reader, actual slot/decoder/ring and seek request.

        The host services the queued seek with av_seek_frame + subtitle reset;
        PS5 audio/video parking, output and clock resets are not simulated.
        """
        if not shutil.which('ffmpeg') or not shutil.which('pkg-config'):
            self.skipTest('Host FFmpeg tools unavailable')
        flags = subprocess.run(
            ['pkg-config', '--cflags', '--libs', 'libavformat', 'libavcodec', 'libavutil'],
            capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('Host FFmpeg development libraries unavailable')
        original = source_file('media/src/evo_subtitle.c')
        adapted = native_subtitles.patch_subtitle_source(original)
        demux = source_file('media/src/evo_demux.c')
        request = region(demux, 'static pthread_mutex_t prospero_seek_mutex =\n',
                         'static int prospero_process_seek_request(void)')
        languages = source_file('media/src/evo_langpref.c')
        playback = source_file('media/src/evo_playback.c')
        clock = region(playback, 'double prospero_media_clock_seconds(void)\n',
                       'static volatile int s_audio_delay_ms')
        facade = next(line for line in playback.splitlines()
                      if line.startswith('double evo_pb_position_s(void)'))
        prelude = r'''
#include <assert.h>
#include <libavformat/avformat.h>
AVFormatContext *play_fmt;
int player_paused, video_stream_index, audio_stream_index = -1;
double media_duration_sec = 60, presentation = 5.5;
double resume_base_offset_seconds = 3, first_video_pts_seconds = 3;
double video_clock_seconds = 5.5;
volatile double audio_clock_seconds = 2.5;
int audio_handle = 1;
long long controls_last_used_ms;
long long now_ms(void) { return 100; }
void toast(const char *title, const char *message) { (void)title; (void)message; }
''' + clock + facade + '\n'
        main = r'''
/* Deliberately use the same AVFormatContext; no reopen or side reader. */
static void read_ahead(void) {
    AVPacket *packet = av_packet_alloc();
    assert(packet);
    while (av_read_frame(play_fmt, packet) >= 0) {
        double pts = packet->pts * av_q2d(play_fmt->streams[packet->stream_index]->time_base);
        if (prospero_subtitle_wants_stream(packet->stream_index))
            prospero_embedded_subtitle_decode_packet(packet);
        int done = packet->stream_index == video_stream_index && pts >= 45;
        av_packet_unref(packet);
        if (done) break;
    }
    av_packet_free(&packet);
}
static void service_seek(void) {
    (void)prospero_seek_in_progress;
    if (!prospero_seek_pending) return;
    assert(av_seek_frame(play_fmt, -1, (int64_t)(prospero_seek_target_seconds * AV_TIME_BASE),
                         AVSEEK_FLAG_BACKWARD) >= 0);
    avformat_flush(play_fmt);
    if (prospero_embedded_subtitle_ctx) avcodec_flush_buffers(prospero_embedded_subtitle_ctx);
    prospero_embedded_subtitle_reset();
    player_paused = prospero_seek_restore_paused;
    prospero_seek_pending = 0;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    assert(avformat_open_input(&play_fmt, argv[1], NULL, NULL) == 0);
    assert(avformat_find_stream_info(play_fmt, NULL) >= 0);
    assert(play_fmt->nb_streams == 3);
    AVFormatContext *reader = play_fmt;
    char text[768];
    for (int paused = 0; paused <= 1; ++paused) {
        assert(av_seek_frame(play_fmt, -1, 0, AVSEEK_FLAG_BACKWARD) >= 0);
        prospero_embedded_subtitle_close();
        prospero_subtitle_requested_stream = -2;
        prospero_subtitle_use_external = 0;
        assert(prospero_sub_slot_start(SUB_PRIMARY, play_fmt, 1, "fixture"));
        read_ahead();
        assert(prospero_embedded_subtitle_text_at(presentation, text, sizeof(text)));
        assert(!strcmp(text, "First current"));
        player_paused = paused;
        assert(prospero_subtitle_select_primary(2));
#ifdef ADAPTED
        assert(prospero_seek_pending && prospero_seek_target_seconds == 5.5);
#endif
        service_seek();
        read_ahead();
        prospero_embedded_subtitle_text_at(presentation, text, sizeof(text));
        printf("switch paused=%d restored=%d requested=%d cue=%s\n",
               paused, player_paused, prospero_subtitle_requested_stream, text);
        assert(play_fmt == reader);
        // Controls: unchanged and external choices must not reset buffered cues.
        int count = prospero_embedded_subtitle_count;
        assert(prospero_subtitle_select_primary(2));
        assert(!prospero_seek_pending && prospero_embedded_subtitle_count == count);
        prospero_subtitle_count = 1;
        assert(prospero_subtitle_select_primary(-1));
        assert(prospero_subtitle_use_external && !prospero_seek_pending);
#ifdef ADAPTED
        assert(prospero_subtitle_requested_stream == -1);
#endif
        assert(prospero_subtitle_select_primary(2));
        assert(!prospero_subtitle_use_external && !prospero_seek_pending);
        assert(prospero_embedded_subtitle_count == count && player_paused == paused);
        // A restart must reopen the explicitly chosen track, not auto-pick SRT.
        assert(prospero_embedded_subtitle_open(play_fmt));
        printf("reopen=%d\n", prospero_embedded_subtitle_stream_index);
    }
#ifdef ADAPTED
    // Decoder-open failure must keep BOTH working tracks and external/off policy.
    assert(av_seek_frame(play_fmt, -1, 0, AVSEEK_FLAG_BACKWARD) >= 0);
    assert(prospero_sub_slot_start(SUB_PRIMARY, play_fmt, 1, "fixture"));
    assert(prospero_sub_slot_start(SUB_SECONDARY, play_fmt, 2, "fixture"));
    prospero_secondary_subtitle_requested = 2;
    read_ahead();
    assert(prospero_embedded_subtitle_text_at(presentation, text, sizeof(text)));
    assert(!strcmp(text, "First current"));
    assert(prospero_sub_slot_text_at(SUB_SECONDARY, presentation, text, sizeof(text)));
    assert(!strcmp(text, "Second current"));
    AVCodecParameters *saved = play_fmt->streams[2]->codecpar;
    AVCodecParameters *broken = avcodec_parameters_alloc();
    assert(broken);
    broken->codec_type = AVMEDIA_TYPE_SUBTITLE;
    broken->codec_id = AV_CODEC_ID_MOV_TEXT;
    broken->width = broken->height = -1; // real avcodec_open2 rejects invalid dimensions
    play_fmt->streams[2]->codecpar = broken;
    prospero_subtitle_use_external = 1;
    prospero_subtitle_enabled = 0;
    prospero_subtitle_requested_stream = -1;
    assert(!prospero_subtitle_select_primary(2));
    assert(prospero_embedded_subtitle_stream_index == 1);
    assert(prospero_secondary_subtitle_stream_index == 2);
    assert(prospero_secondary_subtitle_requested == 2);
    assert(prospero_subtitle_requested_stream == -1 && prospero_subtitle_use_external);
    assert(!prospero_subtitle_enabled && !prospero_seek_pending && player_paused == 1);
    assert(prospero_embedded_subtitle_text_at(presentation, text, sizeof(text)));
    assert(!strcmp(text, "First current"));
    assert(prospero_sub_slot_text_at(SUB_SECONDARY, presentation, text, sizeof(text)));
    assert(!strcmp(text, "Second current"));
    play_fmt->streams[2]->codecpar = saved;
    avcodec_parameters_free(&broken);
    assert(!prospero_subtitle_select_primary(-2));
    assert(!prospero_subtitle_select_primary(99));
    prospero_subtitle_count = 0;
    assert(!prospero_subtitle_select_primary(-1));
    assert(prospero_subtitle_requested_stream == -1 && !prospero_subtitle_enabled);
    // Successful secondary takeover drops only that secondary, then refills.
    assert(prospero_subtitle_select_primary(2));
    service_seek();
    read_ahead();
    assert(prospero_secondary_subtitle_stream_index == -1);
    assert(prospero_secondary_subtitle_requested == PROSPERO_SECONDARY_NONE);
    assert(prospero_subtitle_requested_stream == 2 && prospero_subtitle_enabled);
    assert(prospero_embedded_subtitle_text_at(presentation, text, sizeof(text)));
    assert(!strcmp(text, "Second current") && player_paused == 1);
    // A resumed 18-minute title has only eight seconds on its relative clock.
    // Both audio-master and video-only clocks must keep the absolute position.
    for (int audio = 0; audio <= 1; ++audio) {
        for (int paused = 0; paused <= 1; ++paused) {
            resume_base_offset_seconds = 1072;
            first_video_pts_seconds = 1072;
            video_clock_seconds = 1080;
            audio_clock_seconds = 8;
            audio_stream_index = audio ? 0 : -1;
            media_duration_sec = 3600;
            player_paused = paused;
            int track = prospero_embedded_subtitle_stream_index == 1 ? 2 : 1;
            assert(prospero_subtitle_select_primary(track));
            assert(prospero_seek_target_seconds == 1080);
            assert(prospero_seek_restore_paused == paused);
            prospero_seek_pending = 0;
        }
    }
#endif
    prospero_embedded_subtitle_close();
    avformat_close_input(&play_fmt);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for include in ('include/evo_ntfs.h', 'include/evo_boot_log.h',
                            'media/include/evo_subtitle.h', 'media/include/evo_langpref.h',
                            'media/include/evo_charset.h', 'media/include/evo_audio_out.h',
                            'media/include/evo_subsync.h', 'media/include/evo_demux.h',
                            'media/include/evo_playback.h', 'media/include/evo_packet_queue.h'):
                (directory / Path(include).name).write_text(source_file(include))
            for name, label in (('first', 'First'), ('second', 'Second')):
                (directory / f'{name}.srt').write_text(
                    f'1\n00:00:05,000 --> 00:00:09,000\n{label} current\n\n'
                    f'2\n00:00:40,000 --> 00:00:44,000\n{label} ahead\n\n')
            media = directory / 'tracks.mkv'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=16x16:r=1:d=60',
                '-i', str(directory / 'first.srt'), '-i', str(directory / 'second.srt'),
                '-map', '0:v', '-map', '1:s', '-map', '2:s', '-c:v', 'ffv1', '-g', '1',
                '-c:s:0', 'srt', '-c:s:1', 'ass', str(media)], check=True, timeout=30)
            results = []
            # Keep full real source; discard unrelated functions at link time.
            for index, source in enumerate((original, adapted)):
                results.append(compile_run(
                    prelude + source + languages + request + main, tmp, [media],
                    extra_flags=(['-DADAPTED'] if index else []) + [
                                 '-I', tmp, '-ffunction-sections', '-fdata-sections',
                                 '-Wl,-dead_strip' if sys.platform == 'darwin' else '-Wl,--gc-sections',
                                 '-pthread', *flags.stdout.split()]))
            self.assertEqual(results[0].splitlines(), [
                'switch paused=0 restored=0 requested=-2 cue=', 'reopen=1',
                'switch paused=1 restored=1 requested=-2 cue=', 'reopen=1'])
            self.assertEqual(results[1].splitlines(), [
                'switch paused=0 restored=0 requested=2 cue=Second current', 'reopen=2',
                'switch paused=1 restored=1 requested=2 cue=Second current', 'reopen=2'])

    def test_real_loader_before_after_srt_and_short_webvtt(self):
        original = source_file('media/src/evo_subtitle.c')
        adapted = native_subtitles.patch_subtitle_source(original)
        main = r'''
int main(int argc, char **argv) {
    for(int i=1;i<argc;i++) {
        int n=prospero_subtitle_load_file(argv[i]);
        printf("%d",n);
        if(n) printf(" %.3f %.3f %s",prospero_subtitle_cues[0].start_seconds,
                     prospero_subtitle_cues[0].end_seconds,prospero_subtitle_cues[0].text);
        puts("");
    }
    return 0;
}
'''
        fixtures = [
            '1\n00:00:01,125 --> 00:00:02,250\nHello\n\n',
            'WEBVTT\n\n00:01.125 --> 00:02.250\nHello\n\n',
            'WEBVTT\r\n\r\ncue-id\r\n00:01.125 --> 00:02.250 align:start\r\nHello\r\n\r\n',
            'WEBVTT\n\n00:00:01.125 --> 00:00:02.250\nHello\n\n',
            'WEBVTT\n\n59:59.125 --> 01:00:00.250\nHello\n\n',
            '[Events]\nDialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, value in enumerate(fixtures):
                path = Path(tmp) / f'cue-{i}.srt'
                path.write_bytes(value.encode())
                paths.append(path)
            results = []
            for source in (original, adapted):
                helpers = region(source, 'void prospero_subtitle_trim(\n',
                                 'static int prospero_subtitle_sidecar_path(\n')
                loader = region(source, 'typedef struct {\n    char *text;\n    size_t pos;\n} SubtitleText;',
                                'int prospero_subtitle_load_file_quiet(')
                results.append(compile_run(LOADER_STUBS + helpers + loader + main, tmp, paths).splitlines())
            self.assertEqual(results[0][:5], ['1 1.125 2.250 Hello', '0', '0', '1 1.125 2.250 Hello', '0'])
            self.assertEqual(results[1], ['1 1.125 2.250 Hello'] * 4 + ['1 3599.125 3600.250 Hello', '0'])

    def test_timing_validation_and_truncated_inputs(self):
        source = '#include <string.h>\n#include <assert.h>\n' + native_subtitles.TIMING_PARSER + r'''
int main(void) {
    double a,b;
    const char *bad[]={"", "0", "00", "00:", "00:0", "00:00", "00:00.", "00:00.0", "00:00.00",
      "-01:02.000 --> 00:03.000", "60:00.000 --> 60:01.000", "00:60.000 --> 01:01.000",
      "00:00.0000 --> 00:01.000", "00:00:00.1 --> 00:00:01.000", "00:00:00,000 --> 00:00:00,00",
      "00:03.000 --> 00:02.000", "999999999999:00:00.000 --> 00:00.000", "00:00.000 --> 00:01.000oops"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);i++) assert(!prospero_subtitle_parse_timing(bad[i],&a,&b));
    assert(prospero_subtitle_parse_timing("00:00.000 --> 00:00.000",&a,&b) && a==0 && b==0);
    assert(prospero_subtitle_parse_timing(" 00:01.125\t-->\t00:00:02.250 position:10%",&a,&b));
    assert(a==1.125 && b==2.250);
    assert(prospero_subtitle_parse_timing("0:00:01,125 --> 0:00:02,250",&a,&b));
    assert(a==1.125 && b==2.250);
    /* Exercise every truncated prefix with its own allocation (ASan redzones). */
    const char *s="00:00:01.125 --> 00:02.250";
    for(size_t n=0;n<strlen(s);n++) {
        char *p=malloc(n+1); memcpy(p,s,n);p[n]=0;
        assert(!prospero_subtitle_parse_timing(p,&a,&b)); free(p);
    }
    return 0;
}
'''
        source = '#include <stdlib.h>\n' + source
        with tempfile.TemporaryDirectory() as tmp:
            compile_run(source, tmp)

    def test_real_controller_remote_selection_policy(self):
        original = source_file('core/src/services/PlaybackController.cpp')
        adapted = native_subtitles.patch_controller_source(original)
        setup = region(adapted, '    // Subtitle setup\n',
                       '    /*\n     * Apply the resume position.')
        stubs = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <cassert>
struct ISettingsService { bool enabled=true; bool isAutoSubtitlesEnabled() const {return enabled;} } settings;
struct Application {
 static Application& getInstance(){static Application a;return a;}
 ISettingsService* getSettingsService(){return &settings;}
};
#define EVO_LOGI(...) ((void)0)
#define EVO_LOGE(...) ((void)0)
static int prospero_subtitle_count,prospero_subtitle_requested_stream=-2;
static int prospero_subtitle_enabled,prospero_subtitle_use_external,selections,loads;
static int local_cues,download_status=200,download_result;
static const char *payload="valid",*destination;
static std::string filePath="fixture";
static struct {std::string subtitleUrl="https://fixture.invalid/subtitle";} m_source;
static void *play_fmt=nullptr;
static void prospero_subtitle_clear(){prospero_subtitle_count=0;}
static void prospero_subtitle_load_for_media(const char*){prospero_subtitle_count=local_cues;}
static int prospero_subtitle_select_primary(int track){assert(track==-1);selections++;prospero_subtitle_use_external=1;return 1;}
static int evo_net_http_get_sync(const char*,void*,int,char **body,size_t *len,int *status){
 *len=strlen(payload);*body=(char*)malloc(*len+1);memcpy(*body,payload,*len+1);*status=download_status;return download_result;
}
static const char *evo_data_path(const char*){return destination;}
static int prospero_subtitle_load_external(const char*){loads++;prospero_subtitle_count=strcmp(payload,"valid")?0:1;return prospero_subtitle_count;}
static void prospero_embedded_subtitle_open(void*){}
static void prospero_secondary_subtitle_open(void*){}
static void applyOnlineSubtitles(){}
static void setup(){
'''
        main = r'''
}
static void reset(){selections=loads=local_cues=prospero_subtitle_use_external=0;
 prospero_subtitle_requested_stream=-2;settings.enabled=true;payload="valid";download_status=200;download_result=0;}
int main(int argc,char **argv){
 assert(argc==2);destination=argv[1];
 reset();setup();assert(loads==1 && selections==1 && prospero_subtitle_use_external && prospero_subtitle_enabled);
 reset();settings.enabled=false;setup();assert(loads==1 && !selections && !prospero_subtitle_use_external && !prospero_subtitle_enabled);
 reset();prospero_subtitle_requested_stream=4;setup();assert(loads==1 && !selections && !prospero_subtitle_use_external);
 reset();prospero_subtitle_requested_stream=-1;setup();assert(selections==1);
 reset();payload="invalid";setup();assert(loads==1 && !selections);
 reset();payload="";setup();assert(!loads && !selections);
 reset();download_status=403;setup();assert(!loads && !selections);
 reset();download_result=-1;setup();assert(!loads && !selections);
 reset();destination="/no-such-nuvio-fixture/subtitle.srt";setup();assert(!loads && !selections);
 reset();destination=argv[1];m_source.subtitleUrl="";local_cues=2;setup();assert(!loads && selections==1);
 reset();local_cues=2;settings.enabled=false;setup();assert(!loads && !selections);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            compile_run(stubs + setup + main, tmp, [Path(tmp) / 'remote.srt'], cpp=True)

    def test_adapter_rejects_repeat_or_drift_before_writing(self):
        subtitle = source_file('media/src/evo_subtitle.c')
        controller = source_file('core/src/services/PlaybackController.cpp')
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            s = app / 'media/src/evo_subtitle.c'
            c = app / 'core/src/services/PlaybackController.cpp'
            s.parent.mkdir(parents=True)
            c.parent.mkdir(parents=True)
            s.write_text(subtitle)
            c.write_text(controller.replace(native_subtitles.REMOTE_WRITE, 'changed'))
            with self.assertRaises(RuntimeError):
                native_subtitles.patch_native(app)
            self.assertEqual(s.read_text(), subtitle)
            c.write_text(controller)
            native_subtitles.patch_native(app)
            self.assertEqual(s.read_text(), native_subtitles.patch_subtitle_source(subtitle))
            with self.assertRaises(RuntimeError):
                native_subtitles.patch_native(app)


if __name__ == '__main__':
    unittest.main()
