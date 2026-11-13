/* Folders that hold installed Nuvio title folders. GPL-3.0-or-later.
 * The list is ShadowMountPlus's default scan roots, from
 * drakmor/ShadowMountPlus 8b1f48e086bed93e1ad53158d1103054e362f54d
 * include/sm_paths.h SM_DEFAULT_SCAN_PATHS_INITIALIZER, in its order.
 * ProsperoStore installs only into these roots, so webui/ is at
 * <root>/PPSA99996/webui. Custom scan paths and image installs are not covered. */
#ifndef NUVIO_WEBUI_ROOTS_H
#define NUVIO_WEBUI_ROOTS_H

static const char * const nuvio_webui_scan_roots[] = {
    /* Internal */
    "/data/homebrew", "/data/etaHEN/games",
    /* Extended storage */
    "/mnt/ext0/homebrew", "/mnt/ext0/etaHEN/games",
    /* M.2 drive */
    "/mnt/ext1/homebrew", "/mnt/ext1/etaHEN/games",
    /* USB subfolders */
    "/mnt/usb0/homebrew", "/mnt/usb1/homebrew", "/mnt/usb2/homebrew", "/mnt/usb3/homebrew",
    "/mnt/usb4/homebrew", "/mnt/usb5/homebrew", "/mnt/usb6/homebrew", "/mnt/usb7/homebrew",
    "/mnt/usb0/etaHEN/games", "/mnt/usb1/etaHEN/games", "/mnt/usb2/etaHEN/games",
    "/mnt/usb3/etaHEN/games", "/mnt/usb4/etaHEN/games", "/mnt/usb5/etaHEN/games",
    "/mnt/usb6/etaHEN/games", "/mnt/usb7/etaHEN/games",
    /* USB and external drive roots */
    "/mnt/usb0", "/mnt/usb1", "/mnt/usb2", "/mnt/usb3",
    "/mnt/usb4", "/mnt/usb5", "/mnt/usb6", "/mnt/usb7", "/mnt/ext0", "/mnt/ext1",
    NULL
};

#endif
