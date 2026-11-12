/* Nuvio-only native-title network privilege helper, GPL-3.0-or-later.
 * Process layout follows ps5-payload-sdk v0.43 samples/ps; privilege values
 * follow samples/test_privileges. No offsets or arbitrary PID input.
 *
 * Built twice: `promote.elf` is the one-shot privilege grant, and `nuvio.elf`
 * (NUVIO_WATCH) is the single boot payload. The watch build also serves the
 * browser UI from the installed title folder over loopback, so the port needs
 * no computer on the network; see ui_server.c. */
#include <sys/types.h>
#include <sys/proc.h>
#include <sys/user.h>
#include <sys/sysctl.h>
#include <ps5/kernel.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/stat.h>
#include <fcntl.h>
#include "app_info.h"

/* SDK v0.43's runtime initializes firmware-specific support before main and
 * refuses unknown versions. Do not add a second firmware allowlist here.
 * A successful SDK initialization is not proof of console compatibility. */

/* The browser UI now lives on the console, inside the installed title folder,
 * and this payload serves it on 127.0.0.1, the address the title's own proxy
 * reaches. The document root is derived from the title identity, not scanned. */
#define NUVIO_UI_ROOT "/data/homebrew/PPSA99996/webui"
#define NUVIO_UI_CONF "/data/nuvio/nuvio.conf"
#define NUVIO_UI_PORT 4173
/* Milliseconds to wait after the title appears before changing its credentials.
 * [TESTED-ON-CONSOLE] Writing a title's caps/authid while its PRX modules are
 * still resolving faults the process (0xa0020101 PRX_NOT_RESOLVED_FUNCTION /
 * 0xa0020104 PRX_PROCESS_STARTUP_FAILURE) on a kstuff/fakelib stack. Waiting
 * past that window, but before the title binds its loopback proxy, keeps it
 * alive and lets the bind succeed. */
#ifndef NUVIO_PROMOTE_DELAY_MS
#define NUVIO_PROMOTE_DELAY_MS 500
#endif
int nuvio_ui_server_open(const char *root, int port);
int nuvio_ui_server_poll(int timeout_ms);

#ifndef NUVIO_NO_PROMOTE
static int promote_once(int quiet) {
#ifdef NUVIO_TEST_FW_1270
    if((kernel_get_fw_version() & UINT32_C(0xffff0000))!=UINT32_C(0x12700000)) { puts("NUVIO test refused: requires firmware 12.70"); return 1; }
    puts("NUVIO experimental permission test: firmware 12.70, PPSA99996 only");
#endif
    int mib[4]={CTL_KERN,KERN_PROC,KERN_PROC_PROC,0};
    size_t size=0;
    if(sysctl(mib,4,NULL,&size,NULL,0) || size==0 || size>16777216) return 1;
    unsigned char *buf=malloc(size);
    if(!buf) return 1;
    if(sysctl(mib,4,buf,&size,NULL,0)) { free(buf); return 1; }
    pid_t target=0; unsigned matches=0;
    for(size_t off=0;off<size;) {
        if(size-off<sizeof(struct kinfo_proc)) { free(buf); return 1; }
        struct kinfo_proc *ki=(void *)(buf+off);
        if(ki->ki_structsize<=0 || (size_t)ki->ki_structsize<sizeof(*ki) || (size_t)ki->ki_structsize>size-off) { free(buf); return 1; }
        /* ki_comm costs nothing; sceKernelGetAppInfo is expensive and kstuff
         * patches it. Filter on the name first so a cycle costs one or two
         * calls instead of one per process. [TESTED-ON-CONSOLE] Calling it for
         * every process several times a second collided with a title's startup
         * and produced PRX_PROCESS_STARTUP_FAILURE. */
        if(!strcmp(ki->ki_comm,"eboot.bin") && nuvio_app_matches(ki->ki_pid)) {
            target=ki->ki_pid; matches++;
        }
        off+=(size_t)ki->ki_structsize;
    }
    free(buf);
    if(matches!=1) { if(!quiet) printf("NUVIO promote refused: matches=%u\n",matches); return 1; }
    if(!nuvio_app_matches(target)) return 1;
    uint8_t saved[16],priv[16],check[16]; memset(priv,255,sizeof(priv));
    uint64_t auth=kernel_get_ucred_authid(target);
    if(!auth || kernel_get_ucred_caps(target,saved)) return 1;
    uint64_t privileged=UINT64_C(0x4800000000010003);
    if(auth==privileged && !memcmp(saved,priv,16)) {
        if(!quiet) puts("NUVIO promote verified: privileges already applied");
        return 0;
    }
    usleep((useconds_t)NUVIO_PROMOTE_DELAY_MS * 1000);
    printf("NUVIO promote pid=%d previous_auth=%016lx caps=",(int)target,(unsigned long)auth);
    for(size_t i=0;i<16;i++) printf("%02x",saved[i]); puts("");
    if(kernel_set_ucred_caps(target,priv) || kernel_set_ucred_authid(target,privileged) ||
       kernel_get_ucred_caps(target,check) || memcmp(check,priv,16) ||
       kernel_get_ucred_authid(target)!=privileged) {
        int cr=kernel_set_ucred_caps(target,saved), ar=kernel_set_ucred_authid(target,auth);
        printf("NUVIO promote failed; restore caps=%d auth=%d\n",cr,ar); return 1;
    }
    puts("NUVIO promote verified: native network privileges applied"); return 0;
}
#endif

#ifdef NUVIO_WATCH
/* The title's proxy reads its origin from nuvio.conf. The first boot writes the
 * loopback origin the on-console server listens on; a stored origin is left
 * alone so a deliberate host survives. */
static void ensure_conf(void) {
    FILE *f=fopen(NUVIO_UI_CONF,"r");
    if(f) { fclose(f); return; }
    mkdir("/data/nuvio",0777);
    f=fopen(NUVIO_UI_CONF,"w");
    if(!f) { puts("NUVIO ui: nuvio.conf not writable"); return; }
    fputs("host=127.0.0.1\nport=4173\nhttps=0\n",f);
    fclose(f);
    puts("NUVIO ui: wrote loopback nuvio.conf");
}

static const char *nuvio_ui_detect_root(void) {
    static const char *candidates[] = {
        "/data/homebrew/PPSA99996/webui",
        "/mnt/usb0/homebrew/PPSA99996/webui",
        "/mnt/usb0/PPSA99996/webui",
        "/mnt/usb1/homebrew/PPSA99996/webui",
        "/mnt/usb1/PPSA99996/webui",
        "/mnt/ext0/app/PPSA99996/webui",
        "/mnt/ext0/homebrew/PPSA99996/webui",
        "/mnt/ext0/PPSA99996/webui",
        NULL
    };
    for(int i = 0; candidates[i]; i++) {
        char index[512];
        snprintf(index, sizeof(index), "%s/index.html", candidates[i]);
        int fd = open(index, O_RDONLY);
        if(fd >= 0) { close(fd); return candidates[i]; }
    }
    return NUVIO_UI_ROOT;
}
#endif

int main(void) {
#ifdef NUVIO_WATCH
    /* Loader closes its output socket after the host stops capturing. */
    if(signal(SIGPIPE,SIG_IGN)==SIG_ERR) return 1;
    puts("NUVIO payload ready: PPSA99996 only, firmware support checked by SDK");
    ensure_conf();
    const char *ui_root = nuvio_ui_detect_root();
    if(nuvio_ui_server_open(ui_root,NUVIO_UI_PORT)==0)
        printf("NUVIO ui: serving %s on 127.0.0.1:%d\n",ui_root,NUVIO_UI_PORT);
    else
        puts("NUVIO ui: loopback bind failed");
    fflush(stdout);
    /* One loop, no worker threads: a threaded accept loop in this payload was
     * observed to die after binding (see ui_server.c). The privilege watch runs
     * on the same cadence as before. */
    for(;;) {
        nuvio_ui_server_poll(250);
#ifndef NUVIO_NO_PROMOTE
        (void)promote_once(1);
#endif
        fflush(stdout);
    }
#else
    return promote_once(0);
#endif
}
