/* Nuvio title-local browser assets. SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef NUVIO_LOCAL_UI_H
#define NUVIO_LOCAL_UI_H
#include <stddef.h>

/* Discover the root directory of the packaged webui assets.
 * Checks binary location (KERN_PROC_PATHNAME), external mount candidates,
 * and fallback locations. Returns a pointer to a static null-terminated path. */
const char *nuvio_local_ui_root(void);

/* Caller owns the socket. Return HTTP status, or -1 for an incomplete transfer.
 * root is a trusted installed title directory. Every child component is opened
 * without following symlinks. hook is inserted after the HTML head opening. */
int nuvio_local_ui_send(int fd, const char *root, const char *method,
                        const char *target, const char *hook, size_t hook_len);
#endif
