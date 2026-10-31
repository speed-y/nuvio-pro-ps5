/* Nuvio identity queries, GPL-3.0-or-later.
 * SDK v0.43 samples/ps uses a 96-byte app-info buffer. The title field was
 * observed at byte 16 on 12.70 and 13.60, rather than the sample's byte 20.
 * Match one exact, terminated title inside that API buffer, not process or
 * kernel memory. Unknown layouts without an unambiguous match fail closed. */
#pragma once
#include <sys/types.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef struct { uint64_t words[12]; } nuvio_app_info_t;
_Static_assert(sizeof(nuvio_app_info_t)==96,"SDK app-info buffer size");
int sceKernelGetAppInfo(pid_t, nuvio_app_info_t *);

static inline int nuvio_app_matches(pid_t pid) {
    nuvio_app_info_t info={0};
    if(sceKernelGetAppInfo(pid,&info)) return 0;
    const unsigned char *bytes=(const void *)&info;
    unsigned matches=0;
    for(size_t pos=0;pos+sizeof("PPSA99996")<=sizeof(info);pos++) {
        if(!memcmp(bytes+pos,"PPSA99996",sizeof("PPSA99996"))) matches++;
    }
    return matches==1;
}
