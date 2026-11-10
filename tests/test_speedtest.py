"""Exercise the native speed-test endpoint with deterministic transport results."""
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

from tests.test_native_subtitles import source_file

ROOT = Path(__file__).resolve().parents[1]


class SpeedtestTests(unittest.TestCase):
    def test_native_download_cancel_failures_and_limits(self):
        compiler = shutil.which('cc')
        if not compiler or not shutil.which('pkg-config'):
            self.skipTest('Requires a host C compiler and FFmpeg development libraries')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'libavformat', 'libavutil'],
                               capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('Requires host FFmpeg development libraries')
        harness = r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <libavformat/avio.h>
#include <libavutil/dict.h>
#include <libavutil/error.h>
#include "cJSON.h"
static char response[1024], status[64];
static atomic_int mode, held, opened, file_reads;
static _Atomic int64_t clock_us = 1000000;
static int64_t fake_clock(void) { return atomic_load(&clock_us); }
static AVIOContext discovery_io, download_io;
static const char *discovery = "{\"success\":true,\"data\":["
 "{\"closest\":false,\"region\":\"wnam\",\"url\":\"https://store-1.wnam.tb-cdn.io/dld/100MB.bin\"},"
 "{\"closest\":true,\"region\":\"ceur\",\"url\":\"https://nexus-2.ceur.tb-cdn.st/dld/100MB.bin\"}]}";
static int discovery_read;
static AVIOInterruptCB interrupt;
static void pause_ms(void) { struct timespec t={0,1000000}; nanosleep(&t,NULL); }
static int fake_open(AVIOContext **io, const char *url, int flags,
                     const AVIOInterruptCB *cb, AVDictionary **options) {
 assert(flags==AVIO_FLAG_READ);
 assert(!av_dict_get(*options,"headers",NULL,0));
 assert(!av_dict_get(*options,"cookies",NULL,0));
 assert(!strcmp(av_dict_get(*options,"protocol_whitelist",NULL,0)->value,"https,tls,tcp"));
 assert(!strcmp(av_dict_get(*options,"rw_timeout",NULL,0)->value,"5000000"));
 assert(!strcmp(av_dict_get(*options,"reconnect",NULL,0)->value,"0"));
 atomic_fetch_add(&opened,1);
 interrupt=*cb;
 if(strstr(url,"/api/speedtest?test_length=short")) {
  while(atomic_load(&held) && !cb->callback(cb->opaque)) pause_ms();
  if(cb->callback(cb->opaque)) return AVERROR_EXIT;
  discovery_read=0; *io=&discovery_io; atomic_fetch_add(&clock_us,100000); return 0;
 }
 assert(!strcmp(url,"https://nexus-2.ceur.tb-cdn.st/dld/100MB.bin"));
 if(atomic_load(&mode)==4) return AVERROR(EIO);
 atomic_fetch_add(&clock_us,200000); *io=&download_io; return 0;
}
static int64_t fake_size(AVIOContext *io) { assert(io==&download_io); return 104857600; }
static int fake_read(AVIOContext *io, unsigned char *buffer, int size) {
 if(interrupt.callback(interrupt.opaque)) return AVERROR_EXIT;
 if(io==&discovery_io) {
  if(discovery_read++) return AVERROR_EOF;
  const char *body=atomic_load(&mode)==3 ? "{\"success\":false}" : discovery;
  assert(strlen(body)<(size_t)size); memcpy(buffer,body,strlen(body)); return (int)strlen(body);
 }
 assert(io==&download_io && size<=65536);
 int reads=atomic_fetch_add(&file_reads,1);
 if(atomic_load(&mode)==1 && reads==2) return AVERROR(EIO);
 if(atomic_load(&mode)==5 && reads==2) return AVERROR_EOF;
 atomic_fetch_add(&clock_us,atomic_load(&mode)==2 ? 400000 : 1000);
 memset(buffer,0,(size_t)size); return size;
}
static int fake_close(AVIOContext **io) { *io=NULL; return 0; }
static void respond(int fd,const char *s,const char *type,const char *body,size_t len) {
 (void)fd; assert(!strcmp(type,"application/json"));assert(len<sizeof response);
 memcpy(response,body,len);response[len]=0;snprintf(status,sizeof status,"%s",s);
}
#define av_gettime_relative fake_clock
#define avio_open2 fake_open
#define avio_read fake_read
#define avio_size fake_size
#define avio_closep fake_close
#include "ps5-speedtest.c"
static cJSON *request(const char *method,const char *action) {
 char path[80];snprintf(path,sizeof path,"/evo/speedtest/%s",action);
 serve_speedtest(0,method,path);cJSON *json=cJSON_Parse(response);assert(json);return json;
}
static void expect(const char *field,const char *value) {
 cJSON *json=request("GET","status");
 assert(!strcmp(cJSON_GetObjectItem(json,field)->valuestring,value));cJSON_Delete(json);
}
static cJSON *settled(void) {
 for(int i=0;i<2000;i++) {
  cJSON *json=request("GET","status");const char *state=cJSON_GetObjectItem(json,"state")->valuestring;
  if(strcmp(state,"discovering") && strcmp(state,"downloading")) return json;
  cJSON_Delete(json);pause_ms();
 }
 assert(!"worker did not settle");return NULL;
}
static cJSON *run(int m) {
 atomic_store(&mode,m);atomic_store(&file_reads,0);
 cJSON_Delete(request("POST","start"));assert(!strcmp(status,"200 OK"));return settled();
}
static void check_state(cJSON *json,const char *state) {
 assert(!strcmp(cJSON_GetObjectItem(json,"state")->valuestring,state));
}
int main(void) {
 expect("state","idle");assert(atomic_load(&opened)==0);
 cJSON_Delete(request("GET","start"));assert(!strcmp(status,"405 Method Not Allowed"));
 cJSON_Delete(request("POST","start"));assert(!strcmp(status,"409 Conflict"));
 assert(atomic_load(&opened)==0);speedtest_resume();
 cJSON *json=run(0);check_state(json,"completed");
 assert(cJSON_GetObjectItem(json,"bytes")->valuedouble==104857600);
 assert(cJSON_GetObjectItem(json,"elapsedMs")->valuedouble==1800);
 assert(fabs(cJSON_GetObjectItem(json,"mbps")->valuedouble-466.034)<0.0005);
 assert(!strcmp(cJSON_GetObjectItem(json,"region")->valuestring,"ceur"));cJSON_Delete(json);
 assert(atomic_load(&file_reads)==1600);
 json=run(1);check_state(json,"error");assert(cJSON_GetObjectItem(json,"bytes")->valuedouble==131072);cJSON_Delete(json);
 json=run(5);check_state(json,"error");cJSON_Delete(json);
 json=run(2);check_state(json,"completed");
 assert(cJSON_GetObjectItem(json,"bytes")->valuedouble==2424832);
 assert(cJSON_GetObjectItem(json,"elapsedMs")->valuedouble==15000);
 assert(fabs(cJSON_GetObjectItem(json,"mbps")->valuedouble-1.293)<0.0005);cJSON_Delete(json);
 json=run(3);check_state(json,"error");assert(atomic_load(&file_reads)==0);cJSON_Delete(json);
 json=run(4);check_state(json,"error");cJSON_Delete(json);
 atomic_store(&held,1);cJSON_Delete(request("POST","start"));
 cJSON_Delete(request("POST","start"));assert(!strcmp(status,"409 Conflict"));
 cJSON_Delete(request("POST","cancel"));json=settled();check_state(json,"cancelled");cJSON_Delete(json);
 atomic_store(&held,1);cJSON_Delete(request("POST","start"));
 assert(!speedtest_quiet());json=settled();check_state(json,"cancelled");cJSON_Delete(json);
 assert(speedtest_quiet());cJSON_Delete(request("POST","start"));assert(!strcmp(status,"409 Conflict"));
 speedtest_resume();atomic_store(&held,0);
 discovery="{\"success\":true,\"data\":[{\"closest\":true,\"region\":\"ceur\",\"url\":\"https://tb-cdn.st.attacker.invalid/dld/100MB.bin\"}]}";
 json=run(0);check_state(json,"error");assert(atomic_load(&file_reads)==0);cJSON_Delete(json);
 puts("Native speedtest: throughput, limits, errors, cancellation and playback exclusion passed");
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory)/'test.c', Path(directory)/'test'
            source.write_text(harness)
            for name in ('cJSON.h', 'cJSON.c'):
                (Path(directory)/name).write_text(source_file(
                    ('addons/include/' if name.endswith('.h') else 'addons/src/') + name))
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                            '-I'+str(ROOT/'scripts'), '-I'+directory,
                            str(source), str(Path(directory)/'cJSON.c'),
                            *shlex.split(flags.stdout), '-lm', '-o', str(binary)], check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)
