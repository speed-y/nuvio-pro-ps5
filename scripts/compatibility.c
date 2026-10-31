/* Nuvio process-identification diagnostic, GPL-3.0-or-later.
 * Read-only queries follow ps5-payload-sdk v0.43 samples/ps.
 * Output goes to the loader connection only. No credential changes, signals,
 * file writes or raw process-buffer dumps. This is not a permission test. */
#include <sys/types.h>
#include <sys/proc.h>
#include <sys/user.h>
#include <sys/sysctl.h>
#include <ps5/kernel.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The SDK sample and the observed 13.60 layout both occupy 96 bytes.
 * Search only for our exact title, without assuming either field position. */
typedef struct { uint64_t words[12]; } app_info_buffer;
_Static_assert(sizeof(app_info_buffer)==96,"SDK app-info buffer size");
int sceKernelGetAppInfo(pid_t, app_info_buffer *);

int main(void) {
    puts("NUVIO compatibility diagnostic v2: read-only queries, no file writes");
    uint32_t firmware=kernel_get_fw_version();
    printf("firmware_raw=0x%08x sdk_initialized=yes\n",(unsigned)firmware);
    int mib[4]={CTL_KERN,KERN_PROC,KERN_PROC_PROC,0};
    size_t size=0;
    if (sysctl(mib,4,NULL,&size,NULL,0)) { perror("NUVIO query size"); return 1; }
    if (!size || size>16777216) { puts("NUVIO invalid query size"); return 1; }
    unsigned char *buf=malloc(size);
    if (!buf) { puts("NUVIO allocation failed"); return 1; }
    size_t capacity=size;
    if (sysctl(mib,4,buf,&size,NULL,0)) {
        perror("NUVIO query processes"); free(buf); return 1;
    }
    if (size>capacity) { puts("NUVIO query exceeded capacity"); free(buf); return 1; }
    unsigned candidates=0, matches=0, query_failures=0;
    for (size_t off=0; off<size;) {
        struct kinfo_proc ki;
        if (size-off<sizeof(ki)) {
            puts("NUVIO truncated process record"); free(buf); return 1;
        }
        memcpy(&ki,buf+off,sizeof(ki));
        if (ki.ki_structsize<=0 || (size_t)ki.ki_structsize<sizeof(ki) ||
            (size_t)ki.ki_structsize>size-off) {
            puts("NUVIO invalid process record"); free(buf); return 1;
        }
        if (!memcmp(ki.ki_comm,"eboot.bin",sizeof("eboot.bin"))) {
            candidates++;
            app_info_buffer info={0};
            int rc=sceKernelGetAppInfo(ki.ki_pid,&info);
            if (rc) {
                query_failures++;
                printf("app_info_query_failed rc=0x%08x\n",(unsigned)rc);
            } else {
                const unsigned char *bytes=(const void *)&info;
                for (size_t pos=0; pos+sizeof("PPSA99996")<=sizeof(info); pos++) {
                    if (!memcmp(bytes+pos,"PPSA99996",sizeof("PPSA99996"))) {
                        matches++;
                        printf("nuvio_title_match pid=%d title_offset=%zu buffer_bytes=%zu\n",
                               (int)ki.ki_pid,pos,sizeof(info));
                    }
                }
            }
        }
        off+=(size_t)ki.ki_structsize;
    }
    free(buf);
    printf("eboot_candidates=%u title_matches=%u query_failures=%u\n",
           candidates,matches,query_failures);
    if (matches!=1 || query_failures) {
        puts("NUVIO identification inconclusive; leave Nuvio open and send this output");
        return 1;
    }
    puts("NUVIO identification observed; permissions and UI compatibility remain untested");
    return 0;
}
