# Validation

## What the console tests show

The owner's current console is a retail PS5 on firmware 12.70.
Earlier records below describe firmware 13.60 sessions. Keep each result tied to its recorded firmware and artifact.
The following table summarizes the original 13.60 session, not new 12.70 Media-app testing.

| Check | Result |
|---|---|
| QR login and addon sync | Works. |
| Focused X activation | Works. X activates the selected Nuvio element. |
| Native playback | Works. The log shows `sceVideodec2` decoding H.264 at 1920x800 and 3840x1600. |
| Resumed seeking | Works. Seeking resumes after a short delay. |
| Native EVO addon browsing | Works. |
| Nuvio-branded startup | Works. |
| Playback exit | The log shows the decoder closing and the browser reopening. The restored page itself has no recorded check yet. |

Host checks cover the build and the regression tests. Console logs cover the
recorded native actions. TV observations cover visible behavior. Keep the three
apart.

## Evidence labels

| Label | What the result establishes |
|---|---|
| `[SOURCE-VERIFIED]` | Inspected implementation or a fixed source declaration. |
| `[LOCALLY BUILT]` | Host build, check or mock result. |
| `[TESTED-ON-CONSOLE]` | A recorded console response, console log or TV observation. |
| `[UNKNOWN]` | No sufficient result for this claim. |

Each console result applies to its recorded environment and artifact. A result
for one hash does not certify a later build. The generated receipt keeps
`firmware_validation` as `[UNKNOWN]`.

## Test environment, 2026-10-01

| Item | Recorded value |
|---|---|
| Console | Retail PS5, CFI-1016A 01Y |
| Firmware | 13.60 |
| Entry chain | Relapse, exact resident revision unknown |
| ELF loader | TCP 9021 observed, exact resident build unknown |
| HEN and mount services | etaHEN, ShadowMount, kstuff and helper revisions unknown |
| SDK | v0.43, archive hash in `deps.lock` |
| Target libraries | pacbrew v0.39, archive hash in `deps.lock` |
| Host | macOS, LLVM/lld 23.1.2, Python 3.13.7, Node 22.23.2 |
| FTP | etaHEN service, TCP 1337 observed |
| Native title | `PPSA99997` |

The original session record stays in the private development workspace
`ps5-homebrew-dev`. It holds the private addresses and source URLs. The record
below omits both, and it keeps unknown resident versions as unknown.

## Artifact history

| Artifact | SHA-256 | Result |
|---|---|---|
| Initial native eboot | `f1f1ddac11d47e7e2ffda7b53d0cd857ce960188342f9c66849f58c4a41eed49` | Browser permission failure, then onboarding after promotion |
| Corrected seek eboot | `8ebe32224ba49a71317578f5817ee6df073b95257cd8ef49f7131508fe742483` | Resumed seeking and native addon comparison observed |
| First branded eboot | `c4c02603f479325acfa4031c12c7e0dedc31c758de3c3980728260dfb0ff18b5` | Startup branding observed. Circle left a hidden exit confirmation |
| Corrected exit eboot | `4989d4cabd1f37ade588b2eff66bbb0f1459977ff13aed9e66f93ace4ecd67a8` | Decoder stop and browser reopening in the log |
| Generated runtime | `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036` | Hash checked on the console. Unchanged through these updates |
| Resident watcher | `8cf4bbe0b889b9063a5775b541027f87a2f5599889e655999a0530eaaec83d89` | Ready message, and a later title launch without manual promotion |
| Console UI payload `nuvio.elf` | `b0b41a6f8d8882c2f9d0a61199bbdddfadcd41ea1691f1d2fe8a9740d4702e3d` | Served the whole browser UI from the console with no LAN host |
| Console UI payload `nuvio.elf` with settle | `67bc0d9986bb0abb9b6c719c217fab01470af4f53300cb3fac2cee8c6eb50f44` | Title bound its proxy and loaded the interface from the console |
| Loopback diagnostic eboot (final host build) | `0e4fc05f5f7b42902d65fd9679110745fd7c1e52b10c3d208df9ce96729196da` | Build ID `21524a4a-nuvio-dirty_1007-2338`. Not installed |
| Loopback diagnostic eboot (installed for gate test) | `78d091ee7a352b525bbe1d08a199d64969b4a7aa5a107ca39f9615ab03d13b07` | Build ID `21524a4a-nuvio-dirty_1008-1241`. On-console hash verified. Launch pending |

The rebuilt watcher adds SIGPIPE handling, so it differs from the resident
watcher. It did not replace the resident watcher in this session. Each new upload
needs its own hash and boot record.

## Initial network and input failures

Expected: the title opens Nuvio and allows onboarding.
Observed: EVO rendered, then browser error `WV-109145-0` returned to EVO. The
native log showed host preflight success and loopback bind failure with
`errno=13`. The permission helper applied the required credentials and read them
back. The proxy listened, and the Nuvio page loaded.

Expected: X activates the D-pad selection.
Observed: X first clicked the fixed browser pointer over the QR area. The input
bridge moved activation to the focused Nuvio element. Guest continuation, QR
login and addon sync then worked. The official TV package supplied the public
login configuration.

Recovery: closed and relaunched the title. No firmware, exploit DNS or system
file changed, and no reboot occurred.

## Unpromoted loopback diagnostic

[SOURCE-VERIFIED] The proxy startup now reports `socket`, `bind`, `listen` and
browser connection results as separate log events. `make build` produces the
diagnostic title from the pinned EVO source. It does not load `nuvio.elf` or
`promote.elf` and does not change the title's credentials.

[UNKNOWN] The unpromoted title's loopback bind and browser connection results
remain pending a console run on firmware 13.60. Keep the existing boot helper
and installation flow until this gate passes.

[LOCALLY BUILT] The diagnostic title built from EVO
`21524a4a6effa65312be2026042e44a96efca4c6`. The final `make build` on
2026-10-08 produced `eboot.bin` SHA-256
`0e4fc05f5f7b42902d65fd9679110745fd7c1e52b10c3d208df9ce96729196da` and build ID
`21524a4a-nuvio-dirty_1007-2338`. The signed container inspector reported
authority `0x3100000000000002`, program type `1` and valid integrity. This is
build evidence only. An earlier diagnostic build (`8626ee00…`, build ID
`21524a4a-nuvio-dirty_1007-2327`) went through the blocked transfer attempt.
The updater did not install it.

[TESTED-ON-CONSOLE] On 2026-10-08, the loader and FTP services answered. A
fixed-purpose `control-2.elf` call reported `PPSA99997` installed as an unmounted
folder with fake signing enabled. The diagnostic eboot was not installed. The
update stopped at staged-file verification because SDK `ftpsrv` transforms PS5
containers when FTP `RETR` reads them. The readback is not the file stored on the
console. I removed the staged file. The updater did not rename it over the title
eboot, so the installed title eboot stayed in place.
This matches the FTP readback behavior recorded in private KI-047. The bind gate
is still [UNKNOWN].

[TESTED-ON-CONSOLE] A follow-up used `control-5.elf` to hash the installed and
staged eboots on the console and make a raw rollback copy. It verified and
installed eboot `78d091ee7a352b525bbe1d08a199d64969b4a7aa5a107ca39f9615ab03d13b07`.
`control-2` reported the title still unmounted. The updated eboot has not launched
yet, so socket permission results remain pending.

[TESTED-ON-CONSOLE] On 2026-10-09, the loader (9021) and FTP service (2121)
answered at the owner-supplied address. `control-2.elf` reported the title
installed, fake signing effective and unmounted. `control-3.elf` could not start
it: `running_big_app=8216` and `launch refused: close the running title or sign
in first`. The installed diagnostic eboot did not launch in this attempt. It
produced no socket, bind, listen or browser-connection result. The log read
afterward contained prior build records, so it does not count as evidence for
this attempt. The permission gate remains [UNKNOWN].

### Corrected diagnostic and signing comparison, 2026-10-09

[SOURCE-VERIFIED] The earlier preflight bypass used a C macro that the builder
never enabled. The title could stop before its listener test when the UI helper
was absent. The adapter now inserts the bypass only in diagnostic sources,
without an additional compiler guard.

[LOCALLY BUILT] The corrected native ELF contains the diagnostic bypass message.
Two signed containers use the same compiled module, build ID
`21524a4a-nuvio-dirty_1009-1342`:

| Profile | Eboot SHA-256 | Authority |
|---|---|---|
| Default | `bb55d04d829c15aa149f992ae5e9d38fa6e724c61dc3188a769b1824a5bedb6f` | `0x3100000000000002` |
| SDK install-app example | `4ecb5c7fc811cdaccf5cdb8d51cfd274bf9218594594d96c75de2ac582944da4` | `0x3800000000000022` |

Both pass the container integrity inspection.
The SDK profile embeds the exact 136-byte authentication record from the pinned
SDK example, with its first eight bytes replaced by the example's authority.
Its source file SHA-256 is
`a28a0b34ef75824a9d74ca5895fbeda7256808bf6d2060336cfa35dd9359c3b4`.
The generated runtime remains
`e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036`.

[LOCALLY BUILT] All 35 host tests, documentation checks and source checks passed.
Feedback tests reject old logs, helper mismatches and installed-artifact mismatches.
The release packager rejects diagnostic builds and permission-test signing profiles.

[UNKNOWN] Neither corrected container has a console result yet.
The owner confirmed this boot's jailbreak, closed apps and no Nuvio helper.
The configured console address was unreachable from the host.

Install the corrected default profile first and run the loopback feedback check.
If it fails to bind, close the title and install the SDK profile.
Keep the helper unloaded for both tests.
Use each installed receipt with the updater and preserve its raw rollback copy.
Record fresh listener events separately from UI or playback results.

### Console sequence

1. Run `make check` on the macOS build host.
2. Build with `NUVIO_WORK_DIR=/tmp/nuvio-ps5-hash-build2 make build`.
3. Record the `eboot.bin` SHA-256 from
   `/tmp/nuvio-ps5-hash-build2/build.json`.
4. Jailbreak the PS5 for this boot. Start the normal ELF loader, FTP service and
   ShadowMount.
5. Close Nuvio through the app switcher.
6. Run the updater. It uses `control-5.elf` to hash the installed eboot, save a
   raw on-console backup and verify the staged eboot. Do not upload `nuvio.elf`
   or `promote.elf` for this gate test.

```sh
export PS5_HOST="<console-address>" PS5_FTP_PORT="<ftp-port>"
export PS5_READ_IDLE_TIMEOUT=60
export NUVIO_WORK_DIR="/tmp/nuvio-ps5-hash-build2"
python3 scripts/update.py --previous-receipt "/path/to/installed-build.json"
```

7. Close any foreground big app and return to the dashboard. Keep
   `nuvio.elf` and `promote.elf` unloaded. Launch Nuvio from its home-screen
   tile.
8. Read `/data/nuvio/evo.log` over FTP and record these events separately:
   `server: socket`, `server: bind`, `server: listen`, and
   `server: connection accepted`.
9. Run `control-5.elf` again. Compare its on-console installed hash and the
   logged build ID with the candidate receipt. Record the console model, resident
   support-stack versions, exact command, output and recovery in the private
   hardware log.

The `connection accepted` event excludes the proxy's internal shutdown wake-up.
If bind succeeds, the browser must produce an accepted connection before this
gate passes. A load error for the missing UI server does not change the socket
results.

## Baseline native playback and seeking

Expected: a stream opens, native frames appear, and seeking resumes playback.

One source returned HTTP 403 before the decoder started. Another source played.
The original seek guard rejected provider playback with an empty local path, and
the controller still entered seeking, which froze playback.

The corrected seek build accepts valid provider demuxers. Seeking then resumed,
with some delay compared with other devices. The log identified native H.264
decoding at 1920x800 and 3840x1600. One recorded seek settled in 1107
milliseconds.

```text
PlaybackController: video decoder opened (backend=NATIVE (sceVideodec2), codec=27, 1920x800 @ 23.98 fps)
web: startPlaybackSource -> ok
bc SEEK_AVFRAME rc=0 ts=1980929 strm=0 target=165.243 ms=0
bc SEEK_SETTLE ms=1107 disc=12 pts=165.249 vrel=0.000 arel=0.000 aq=9
EVO vdec native: CLOSE decodes=190 framesout=169 fatal=0
```

The updater checked old files, staged bytes and backups under `/data`. It
imported five private synced addons and the local test addon into the native
settings. A fresh title launch returned `launch_result=0x8018` and started the
proxy without manual promotion.

## Branded startup and exit correction

Expected: automatic startup and playback transitions hide the EVO menus.

The first branded update replaced eboot, icon, launch images, loading RML and
wordmark. `control-2` reported an installed folder with `mounted:false` before
the replacement. The updater checked predecessors, backups and new bytes.
`control-3` reported `running_big_app=-1` and `launch_result=0x4018`. The console
fetched the rebuilt UI assets with HTTP 200.

Nuvio-branded startup worked. Circle then displayed `Opening Nuvio` without
stopping playback, and a second Circle returned to video.
[SOURCE-VERIFIED] The loading screen hid the native exit confirmation while
playback stayed active.

The correction stops Nuvio playback directly on Circle. It keeps active playback
overlays and the native settings confirmation. The corrected launch returned
`running_big_app=-1` and `launch_result=0xe018`.

The corrected log identifies build `21524a4a-nuvio_1001-1551`. It opened a native
decoder with codec 173 at 1920x1080, settled a seek in 1662 milliseconds, closed
the decoder with 263 decodes and 253 output frames and no fatal result, then
reopened the browser.

```text
bc SEEK_SETTLE ms=1662 disc=42 pts=358.733 vrel=0.000 arel=0.000 aq=9
EVO vdec native: CLOSE decodes=263 framesout=253 fatal=0
web: sceWebBrowserDialogOpen -> 0x00000000
```

Recovery backups stay below `/data/homebrew/ps5-homebrew-dev`. The runtime and the
artwork did not change during the exit correction. No reboot or system write
occurred.

## Nuvio 1.2.2 update, 2026-10-03

[TESTED-ON-CONSOLE] The pinned Nuvio source moved from 1.2.1 to 1.2.2
(`358d08cf`), and the official TV configuration moved to the 1.2.2 package.
The EVO pin did not move: `main` at `21524a4a` is still the newest revision, and
the newest EVO release asset is older than that commit. The rebuild changed only
`eboot.bin` in the title inventory. The runtime, artwork and loading RML stayed
byte-identical.

[TESTED-ON-CONSOLE] The first rebuild did not start. Six launches returned an
accepted `launch_result` (`0x18` to `0xa018`, low value varying per launch)
while `promote.elf` matched no running `PPSA99997` process and
`/data/nuvio/evo.log` gained no byte. Restoring the previous eboot `4989d4ca`
and launching again made the process visible to `promote.elf` and resumed the log.

[SOURCE-VERIFIED] The cause was the link, not the sources. The packaging step
expands `${PS5_SYSROOT}/lib` with a shell glob, and with `--as-needed` the first
stub that satisfies a kernel symbol is the one recorded in the module's import
table. Under the ambient UTF-8 collation `libkernel_web.so` sorted before
`libkernel.so`, so the module imported `libkernel_web.prx`, the browser-safe stub.
The working build imports `libkernel.prx`. `scripts/build.py` now pins `LC_ALL=C`
and [Build](BUILD.md) explains why.

[TESTED-ON-CONSOLE] With that fix the rebuilt title starts and runs. The log
records `BUILD 21524a4a-nuvio-dirty_1003-1441`, the proxy hook injected into `/`,
660718 bytes of browser storage restored and the route `home`. An accepted launch
response is still not execution: check `promote.elf` and the log build string
every time.

[TESTED-ON-CONSOLE] A launch sometimes needs several attempts before the title
stays up. One attempt in this session failed the same way. Treat a single failed
launch as inconclusive and retry before you record a failure.

[TESTED-ON-CONSOLE] During this session, catalogue entries and thumbnails failed
to load across the app. The console's DNS connectivity caused it, not this
change. The app recovered when connectivity did.

[LOCALLY BUILT] A white flash appears between the native splash screen and the
Nuvio interface when a stream exits, visible in a dark room. The served
`index.html` carries
`<style>html,body{background-color:#000;margin:0}</style>` as its first head
element, applied through `patch_index()` and covered by host tests.

The port tried a `media="print"` stylesheet that switched to `all` on load, to
stop the 544 KB `css/bundle.css` holding back the first paint. The console's
browser then rendered Nuvio unstyled, so the pattern is not usable here and the
build keeps the plain render-blocking `<link>`. The visible transition still
needs a console check.

[TESTED-ON-CONSOLE] The build now installs the repository artwork in
`assets/icon.png` (512x512) as the title icon. The console copy verified
byte-for-byte at `90ed6493`, and the previous icon (1fe88349) stays under
`/data/homebrew/ps5-homebrew-dev`. The PS5 caches a title icon. A second
registration reported `changed:false` and left the icon URL stamp at
`v=1790864733-28006`, so the home-screen tile keeps the old artwork until the
console recreates the title record.

## Console serves its own UI, 2026-10-03

[TESTED-ON-CONSOLE] The browser UI now travels inside the title folder and the
boot payload serves it, so no computer runs while you use the app.

- Artifact: `nuvio.elf`
  `b0b41a6f8d8882c2f9d0a61199bbdddfadcd41ea1691f1d2fe8a9740d4702e3d`.
- Folder: the build's `webui/` (117 files, 17 MB) copied into
  `/data/homebrew/PPSA99997/` and verified byte-for-byte over FTP.
- Configuration: `/data/nuvio/nuvio.conf` with `host=127.0.0.1`, `port=4173`,
  `https=0`.
- Command: push `nuvio.elf` to loader 9021, then launch `PPSA99997`.
- Expected: the title opens its own interface and no LAN host answers.
- Observed: with the host UI server stopped, the payload printed
  `NUVIO ui: serving /data/homebrew/PPSA99997/webui on 127.0.0.1:4173` and the
  console fetched 68 UI requests (`/`, `/index.html`, `/css/bundle.css`,
  `/app.bundle.js`, `/res/i18n/en.json`, `/assets/libs/hls.min.js`). The native log
  records `proxy: injected hook into / (2568 bytes)` and `page: route authQrSignIn`.
- Recovery: the console keeps the previous origin at
  `/data/nuvio/nuvio.conf.before-console-ui`.

[TESTED-ON-CONSOLE] The session measured two approaches and rejected one. A
payload listener bound to the console's own LAN address is reachable from another
machine, but the title's proxy did not load the page from that address
(`page watchdog: ... did not load`), so the working origin is loopback. A threaded
accept loop inside the payload bound the port and then stopped answering. The
payload now drives one single-threaded accept loop from its own thread of control.

The visible transition still needs a console check. The session found the
credential timing that blocked the launch later the same day, in
[Console UI working end to end](#console-ui-working-end-to-end-2026-10-03).

## Console UI working end to end, 2026-10-03

[TESTED-ON-CONSOLE] After a fresh install of the title from this build, the app
launched, bound its proxy and loaded the interface from the console with no
computer running.

- Install: all 223 files of `output/app/PPSA99997/` written to
  `/data/homebrew/PPSA99997` (68,133,019 bytes). The installed tree matches
  `build.json` exactly.
- Module: `eboot.bin` 38,847,060 B sha256 `f7ea5526…` and `sce_module/libc.prx`
  1,284,674 B sha256 `e6ff45d1…`, both read on the console with a payload.
- Payload: `nuvio.elf` sha256 `67bc0d99…`.
- Observed: `web: server: 127.0.0.1:8686 ready, proxying http://127.0.0.1:4173`,
  `web: proxy: injected hook into / (2568 bytes)`, `web: storage: restored 717849
  bytes`, `web: page: route home`, and 104 requests in `/data/nuvio/ui.log`.

[TESTED-ON-CONSOLE] Two faults had to be fixed first.

The payload scans for the title process and grants it the credentials its
loopback bind needs. Writing those credentials while the title's PRX modules
still resolve faults the process. The session measured three timings on one boot:

| Credential write | Result |
|---|---|
| immediately on detection (~0.25 s) | `PRX_PROCESS_STARTUP_FAILURE` or `PRX_NOT_RESOLVED_FUNCTION` |
| delayed 2500 ms | app runs, `bind/listen 127.0.0.1:8686 failed errno=13`, `WV-109145-0` |
| delayed 500 ms | app runs and binds, interface loads |

The payload now waits 500 ms (`NUVIO_PROMOTE_DELAY_MS`). The scan also stopped
calling `sceKernelGetAppInfo` for every process each cycle, a call kstuff patches
(`[kstuff.elf] … sceKernelGetAppInfo: Broken pipe`). This timing is the likely
explanation for the older "a launch can take several attempts" note.

[TESTED-ON-CONSOLE] A raw-ELF `eboot.bin` cannot start. The system rejects it
before the app runs: `sceSblAuthMgrAuthHeader returned unexpected error 46` and
`sceSblACMgrGetFsSandboxType(.../eboot.bin) failed. 0x80020008`. Deploy the
converted `output/app/PPSA99997/eboot.bin`, never the `.build/eboot.elf`.

## Host coverage

### Hash-helper deadline, 2026-10-09

[SOURCE-VERIFIED] The installer previously killed helper subprocesses after
40 seconds, while the eboot hash helper allowed 60 seconds between reads.
The parent now covers connection, transfer and response budgets.
It also follows a longer configured response timeout.

[LOCALLY BUILT] `make check` passed all 25 tests, documentation checks and
private-artifact checks. The regression checks default and extended hash-helper
deadlines. This change needs no native rebuild.

[LOCALLY BUILT] Eight host regressions pass. They cover the HTTP handler, browser
focus, provider seek, control responses, saved routes and Circle behavior. The
seek and Circle tests run the patched upstream code against host fixtures. These
tests use no console and no PS5 SDK. GitHub CI runs the host checks on Ubuntu.
The native title builds through the macOS adapter.

## Acceptance procedure

Use a receipt for the exact installed artifact. Keep a filtered private log and a
record of the visible behavior.

1. Start from a fresh jailbreak when you test boot behavior.
2. Push exactly one payload, `nuvio.elf`, for that boot.
3. Launch the title.
4. Check Nuvio branding during startup.
5. Check guest access and focused X activation.
6. Check QR login and addon sync.
7. Play the generated test clip.
8. Check the moving picture and the tone.
9. Pause and resume playback.
10. Seek forward and backward several times.
11. Press Circle once.
12. Check the restored Nuvio page and selection.
13. Open Player settings.
14. Check native addon playback and its stop confirmation.
15. Close the title through the app switcher.
16. Relaunch the title.
17. Record the subtitles, formats and session durations you tested.

Generated test picture and audio, pause, subtitles and longer stability are still
open. Fresh-boot behavior with the console UI payload is also open, and the
visible playback-return transition still needs a console check.

## Record a new result

Include every field below.

| Field | Required record |
|---|---|
| Environment | Firmware, console model, exploit, loader, SDK, HEN and mount versions |
| Artifact | Source pins, eboot hash, runtime hash and helper hashes |
| Command | Exact command with private values removed from the public copy |
| Expected result | Visible behavior or response that defines success |
| Observed result | What the TV showed and the filtered console evidence |
| Recovery | Close, rollback, reboot or other action actually used |
| Limits | Open tests and unknown version identities |

Keep failed attempts when you add a corrected result. Keep raw logs and receipts
with private state outside Git.

## Title-local UI experiment, 2026-10-09

[LOCALLY BUILT] Native build command:

```sh
NUVIO_WORK_DIR=/tmp/nuvio-ps5-title-ui-20261009 python3 scripts/build.py --auth-profile sdk-install-app --title-ui
```

Build `21524a4a-nuvio-dirty_1009-1353` has eboot SHA-256
`5298741976bf73ffa25b41420527967c23845b7484973c6a15768847fbaa5009`,
runtime SHA-256
`e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036`,
`ui_hosting: title`, `auth_profile: sdk-install-app` and no diagnostic mode.
Container integrity passed. It uses the same runtime as the two corrected
permission diagnostics. The console still has the previous diagnostic.

Seven host tests passed with AddressSanitizer and UndefinedBehaviorSanitizer.
They exercise the actual C responder over sockets: HTML bridge insertion, HEAD,
large streamed assets, traversal and symlink rejection, missing files, oversized
HTML and a disconnected browser. These are host results.

[UNKNOWN] Firmware startup and packaged-file access remain open. After comparing
the two permission diagnostics, install this title-local build, run the feedback
command with its receipt and observe the UI without either Nuvio helper loaded.
The UI gate requires fresh bind/listen/connection, packaged asset status 200 and
a Nuvio route. Then test generated video, sound, pause, seek, Circle return and
relaunch. Record the full environment tuple in the private hardware log.

## Corrected signing comparison, 2026-10-09

[TESTED-ON-CONSOLE] On firmware 13.60, with a current jailbreak and neither
Nuvio helper loaded, the corrected default-profile diagnostic launched and
reported `server: socket ok fd=25` followed by
`server: bind failed port=8686 errno=13`. Raw staging and installed hashes matched
`bb55d04d829c15aa149f992ae5e9d38fa6e724c61dc3188a769b1824a5bedb6f`.

The SDK-example profile of the same compiled module installed with raw hash
`4ecb5c7fc811cdaccf5cdb8d51cfd274bf9218594594d96c75de2ac582944da4`.
Two accepted launches produced no fresh BUILD or socket events within the
30-second observation windows. The status response reported an unmounted title between attempts.
[UNKNOWN] Its bind behavior remains unknown. The metadata needs a launch
investigation before adoption. The title-local UI variant has no console result.

The private hardware log records the full environment tuple, commands and
backup evidence. No UI assets, runtime, settings or accounts changed during
this eboot-only comparison.

[TESTED-ON-CONSOLE] Follow-up owner observation: the SDK-profile title shows PRX
startup error `0xa0020101` and does not open. Restored the default diagnostic
with raw staged and installed hash verification. The default profile's measured
unpromoted bind failure remains unresolved. The private hardware log records
the restoration command and evidence.

## Default authority with SDK info and automatic closure, 2026-10-09

[TESTED-ON-CONSOLE] Retained default authority `0x3100000000000002` and signed
the same diagnostic module with the remaining SDK example auth info. Candidate
eboot sha256: `8ca26000911fdb4534eaa376c669d3da54ae39a338305902bedc856e7749a897`.
Raw staging and installed hashes matched, but an accepted launch produced no
fresh BUILD/socket events within 30 seconds. No bind result established.

Restored the default diagnostic, then observed its fresh BUILD, socket success
and bind failure errno=13. The new fixed-title close helper then returned process
evidence, and the close command verified the title unmounted. Close helper sha256:
`6cf9959af530d9b23bfc25fbe2cb68f0c7481eba2526ca8ad61effceb99a6053`.
The private hardware log records commands, tuple, rollback and filtered logs.

[UNKNOWN] Network permissions inside the title remain unresolved. Both SDK
auth-info variants remain experiments.

## Embedded promotion and page crash, 2026-10-09

[TESTED-ON-CONSOLE] Firmware 13.60, SDK v0.43, existing loader TCP 9021,
FTP v0.21.1 TCP 2121. Exploit, loader and HEN revisions remain unknown.
No Nuvio helper was manually loaded before the comparison.
Updates used `scripts/update.py --previous-receipt` with preserved eboot-only
receipts. Feedback used `scripts/feedback.py --gate ui`.

Descriptor-mode changes failed before connection: fcntl returned errno13,
and ioctl(FIONBIO) returned errno13. Socket creation with SOCK_NONBLOCK worked.
Eboot SHA-256: `dc0fbf4f35cd90795f60fc98ad080da1c7fbe21b404dedfc43aad83b76c15a9f`.
Embedded promotion ELF SHA-256:
`502ae8189cda8dbe0b82c6dc2b11a1c932dba6f4773e455e5ac532bb999eb952`.
Fresh BUILD `21524a4a-nuvio-dirty_1009-1456` recorded promotion verification,
bind/listen success and browser connection accepted. Feedback verified no page response or route. The owner saw Opening Nuvio, a white screen, then a crash.

The kernel log reported SIGSYS in eboot.bin. The matching app return address
maps to conn_thread immediately after nuvio_local_ui_send.
[INFERENCE] openat in the responder is the likely unsupported syscall.
The next comparison uses ordinary open with O_NOFOLLOW on each path component.
Updates keep the title closed while replacing its files.
The private environment hardware log holds exact commands, hashes, logs and recovery.
Full page, playback, repeated launch and fresh-boot checks remain pending.

## Ordinary file opens reach the home route twice, 2026-10-09

[TESTED-ON-CONSOLE] Same boot and environment as the preceding experiment.
Eboot SHA-256: `56f7b86cf867e0c36a031f392dca7ecd05383313a7791cb836f30625c0552e6a`.
Embedded promotion ELF SHA-256:
`a505a32a369488fc4ae35df6c3b98d9a862af070f407309a11d89c4b719b5934`.
The updater verified raw staged and installed bytes before replacement.

The responder uses ordinary open/O_NOFOLLOW on each path component.
Two `scripts/feedback.py --gate ui` runs automatically closed and relaunched the title.
Both verified embedded promotion, bind/listen, packaged HTTP200 responses,
`page: route home` and `Feedback: ui_route_observed`.
No Nuvio helper was manually uploaded. The private hardware log records commands
and recovery. Existing runtime, UI assets and settings remain installed.
Playback, a full asset update and a fresh-jailbreak launch remain pending.

[TESTED-ON-CONSOLE] Owner confirmed playback, seeking and Circle return all work
on the ordinary-open build. This observation uses the existing installed UI assets.

## Complete file update, 2026-10-09

[TESTED-ON-CONSOLE] Reconciled the installed artwork and 117 browser assets
against read-only FTP hashes. The first attempt refused an asset missing from
the old receipt. The reconciled predecessor let the full updater complete.
The native and embedded helper hashes match the ordinary-open entry above.

The full receipt's changed files passed staged readback checks.
Fresh feedback then verified embedded promotion, listener, HTTP200 assets and
`page: route home`. Settings stayed in `/data/nuvio/`.
The private hardware log holds the exact commands and recovery receipts.

[LOCALLY BUILT] The store zip carries the complete PPSA99997 folder.
The single-install package omits separate boot-payload release assets.
Fresh-jailbreak startup and the eventual published release remain pending.

## Fresh-jailbreak startup, 2026-10-09

[TESTED-ON-CONSOLE] Owner restarted the console, ran Relapse and the normal
services, and left Nuvio closed with no Nuvio helper loaded. Same endpoint.
The complete ordinary-open build then passed receipt-verified feedback:
embedded promotion, bind/listen, packaged HTTP200 and route profileSelection.
The private hardware log records the exact command and full environment tuple.

## Alpha.4 artwork build, 2026-10-09

[LOCALLY BUILT] Replaced the title icon with the supplied 512×512 logo and both
launch images with the supplied 1920×1080 wallpaper. The title content version
is `01.000.004`. `make check`, `NUVIO_WORK_DIR=/tmp/nuvio-alpha4-build make
build` and `NUVIO_WORK_DIR=/tmp/nuvio-alpha4-build make release` passed.

The local `PPSA99997.zip` SHA-256 is
`e50bb82f809f459149374a468087c4ea8d0cd1cb755995d10afa24823063ebce`. Its
`eboot.bin` SHA-256 is
`10794a7e86151ee32157209ab7c58256a53b62cd777985f7e1c41a62918224be`.
The icon SHA-256 is
`d5a3f3d4288081e055cd1013e61f61d2e8ac4af80172cd3c30da1cbf7b4cb3c4`, and both
launch images have SHA-256
`e4d78b2eb802a94c2c7dd02ce8fed16932ebb92541470698cd6f56b32b8ecf66`.

[LOCALLY BUILT] The published alpha.4 `PPSA99997.zip` SHA-256 is
`7173168bded10ebf703502b3db7db99b5a3f2717c6c18ef23456e435eae79e94`. Its
`eboot.bin` SHA-256 is
`55d112286955a973fab49574d97c610ad9ff1b5fe5a89e20938bcdc82dcf770b`. The
release archive passed `unzip -t`. Its icon and launch images match the source
asset hashes above.

[UNKNOWN] We have not installed alpha.4 on the console. Install that exact
`PPSA99997.zip`, run receipt-verified feedback, and record the observed eboot
hash and launch artwork in the private hardware log.


## Playback profile and route return, 2026-10-09

[COMMUNITY] Owner reports alpha.4 returns to "Who's Watching?" after playback.
[SOURCE-VERIFIED] Browser recreation loses the in-memory profile-selection flag.
The startup profile picker runs before route restoration. The original resume
filter also excludes title and stream screens.

The native handoff now saves the selected profile and preceding route before
synchronously saving browser storage. Its return URL includes `nuvioPlaybackReturn=1`.
Startup consumes this saved selection once, checks the active profile still exists,
and restores title, stream or home routes. Ordinary launches retain the picker.
The return snapshot lasts 24 hours. Restoring it refreshes the route timestamp,
so the original 20-minute route limit does not expire during a movie.
Guest startup uses the same return check. Other platforms retain their resume filter.

[LOCALLY BUILT] `make check` passed with 53 tests. The full title build passed:

```sh
NUVIO_WORK_DIR="$PWD/build/playback-return" make build
```

The receipt and update ZIP are in `build/playback-return/`.
`write_store_zip` checked every title file against `build.json` and created the ZIP. ZIP SHA-256: `82b61e1f1bf535f167c8654a2e3a8196d9211a19c2baeaa50a434d94ce86c1e2`.
Eboot SHA-256: `39dbbef26055f352794805e2cb8a9bef106253d1d0a3d67f89c7fb4d8f4daa07`.

[UNKNOWN] Console validation remains pending:

1. Close Nuvio and save the installed receipt and raw eboot backup.
2. Update with the new complete receipt and run fresh UI feedback.
3. Select a profile with Remember last profile disabled, open a title and play.
4. Press Circle. Confirm the same profile and title or stream page return.
5. Play again, then check natural playback end and a failed stream return.
6. Repeat with a PIN profile, guest profile and playback longer than 20 minutes.
7. Close and reopen the title. Confirm the ordinary profile picker still appears.

Use the updater and feedback commands in [Build](BUILD.md#fast-console-loop).
Record console versions, installed hashes and visible results before a release.


### Playback return update installation, 2026-10-09

[TESTED-ON-CONSOLE] The updater closed Nuvio and verified the unmounted title state.
It replaced only eboot and `webui/app.bundle.js`, preserving settings.
The console-side helper verified raw eboot SHA-256 `39dbbef26055f352794805e2cb8a9bef106253d1d0a3d67f89c7fb4d8f4daa07`.
The UI bundle readback matched SHA-256 `c6723b9190ffbac4efee2b3c61eec6f90e28217c0a04758bbcfd9439615f8385`.

Feedback verified the installed eboot, but the launch helper refused startup.
A separate launch attempt reported `running_big_app=49176` and
`launch refused: close the running title or sign in first`.
The private hardware log records commands and rollback files.

[UNKNOWN] Close the active app or sign in, then open Nuvio and perform the
playback return checks above. The launch refusal prevented UI and playback return checks.


### Owner playback return confirmation and alpha.5 package, 2026-10-09

[TESTED-ON-CONSOLE] Owner confirmed "it works" after installing the playback-return
build and testing the reported exit behavior. The installed eboot and UI bundle
hashes are those in the preceding entry. This confirms the reported return fix.
The private hardware log records the environment and installation commands.

[LOCALLY BUILT] Alpha.5 packages the same tested native binary and UI bundle.
Only `sce_sys/param.json` changes to content version `01.000.005`.
`VERSION` is `0.1.0-alpha.5`. The receipt records the updated metadata hash.
The release therefore keeps the tested playback code and browser bundle.
Separate natural-end, long playback and guest/PIN cases remain pending.

[LOCALLY BUILT] Alpha.5 store ZIP SHA-256:
`15310094f8c65dcca45a0714e8c94316898f9afe83412e2438be1a072f4bf486`.
The package retains the recorded eboot and UI hashes.

## EVO 0.12.0 update, 2026-10-10

[SOURCE-VERIFIED] The build pins EVO to the v0.12.0 release commit
`9ee9a5420c73b5be448610e5f0a90a29a75592f3`.
The title retains upstream passthrough, receiver probing and PCM fallback.
Player settings exposes Settings > Audio > Audio Passthrough.
The controller reads this setting when a new stream starts.
The adapter verifies EVO's provider-seek fixes without rewriting them.

The inherited update also pins Nuvio TV and its public login configuration to
1.2.3. SDK v0.43 and pacbrew v0.39 remain fixed.
EVO requires FFmpeg 7.1.1 and its pinned homebrew UI submodule.
The adapter builds FFmpeg from source and unpacks the UI submodule archive.
The FFmpeg compiler prefix now expands the actual SDK directory.

[LOCALLY BUILT] All 58 host tests, documentation and source checks passed.
The complete native build passed with signed-container integrity checks.
The receipt covers 237 title files and eight helpers.
Artifacts and logs remain under `build/evo-0120/`.

| Artifact | SHA-256 |
|---|---|
| `PPSA99997.zip` | `c1055179489bf98410d890e209841b3abc1082ffe8fc6999b10f50a17ec50829` |
| `eboot.bin` | `ec58cbe0f94e4b2db2e61800545218c0664f8efb0307cbaf92a16ff098c7a720` |
| `webui/app.bundle.js` | `84109831940e1e21b85bbc5983f12b8098754a9e9fa9adcabcfe4cda0a91d50e` |

[LOCALLY BUILT] An uncached FFmpeg configure, compile and install passed on macOS.
The release uses content version `01.000.006` and version `0.1.0-alpha.6`.
Build and package commands:

```sh
export NUVIO_WORK_DIR="$PWD/build/evo-0120"
make check
make build
make release
```

[UNKNOWN] Console playback and passthrough for this build remain pending.
The startup result appears in the following session record.
The local archives are held for testing before GitHub publication.

1. Boot firmware 13.60 and run the jailbreak, ShadowMount and loader on 9021.
2. Close foreground apps and confirm the installed predecessor receipt.
3. Update the complete title, preserving `/data/nuvio` and the raw eboot backup.
4. Run fresh UI feedback and confirm the new BUILD line and packaged home route.
5. Play with passthrough disabled. Check sound, pause, seeking and Circle return.
6. Enable Audio Passthrough in Player settings > Settings > Audio.
7. Open a Dolby Digital stream and record the receiver's format display and sound.
8. Repeat with Dolby Digital Plus, DTS and AAC supported by the connected receiver.
9. Switch streams and audio tracks. Check sound resumes and seeking remains usable.
10. Disable passthrough, start another stream and confirm PCM output returns.
11. Close and reopen Nuvio. Check settings and the playback return profile remain correct.

Use the console host and FTP port configured in [Operations](OPERATIONS.md).
Use the same work directory for update and feedback:

```sh
python3 scripts/update.py --previous-receipt config/installed-build.json
python3 scripts/feedback.py --gate ui
```

Record receiver model, HDMI connection, source codec, displayed format and sound.
Record exact installed hashes and the full console environment tuple.
Test TrueHD separately: upstream labels that passthrough path experimental.


## EVO 0.12.0 startup, 2026-10-10

[TESTED-ON-CONSOLE] The alpha.6 player launched on firmware 13.60 and reached the
Nuvio home route. The console model was CFI-1016A 01Y. The build pinned SDK v0.43 and pacbrew v0.39. Resident exploit, loader, HEN and mount-service revisions remain unknown.

Before replacement, the raw player hash and 235 noncontainer files matched the
previous receipt. The update verified the staged and installed player hashes.
The update retained the runtime module without downloading it again.

Eboot SHA-256: `ec58cbe0f94e4b2db2e61800545218c0664f8efb0307cbaf92a16ff098c7a720`.
Browser bundle SHA-256: `84109831940e1e21b85bbc5983f12b8098754a9e9fa9adcabcfe4cda0a91d50e`.

`scripts/feedback.py --gate ui` reported build `9ee9a542-nuvio_1010-0357`, successful
promotion, packaged responses 200 and `page: route home`.
The owner reports startup, playback and exit work. Smaller Penguplay streams seek normally.
Large UsenetStreamer streams can stall after seeking. Pause/resume often restores playback.
The log shows failed chunk reads and repeated HTTP429 responses with six connections.
[Issue #4](https://github.com/bilawalriaz/nuvio-ps5-homebrew/issues/4) tracks the seek problem.
The owner chose to publish alpha.6 and address seeking separately.
An explicit receiver format and codec observation remains pending.


## Network seek fix, 2026-10-10

[SOURCE-VERIFIED] The adapter replaces EVO's parallel HTTP reader with FFmpeg
range reads. Provider headers and playlist behavior remain intact. HTTP429 and
HTTP503 reconnects follow the existing retry budget and respect Retry-After.

[LOCALLY BUILT] The local HTTP test advertised a 256 MiB file with a two-response
limit. Six readers made 222 requests and received 166 rate-limit responses.
The adapted reader made nine requests and received one rate-limit response.
All five adapted range seeks passed. A permanently limited endpoint failed after
two requests in 1.2 seconds. The probe and adapter passed ASan and UBSan checks.
Host FFmpeg was 9.0.1. The console build uses pinned FFmpeg 7.1.1.

[TESTED-ON-CONSOLE] A separate I/O probe on firmware 13.60 opened the same
22 GB UsenetStreamer source and passed nine seeks, including 371.664 and 835.083 seconds.
The probe used the adapted source and the pinned console FFmpeg libraries.
Probe SHA-256: `d02f7ae36f6fee34cbb43444a390a123b9f600e8d690892112d54bdfa3ed13ff`.

A temporary development build enabled EVO's existing remote controls.
The player decoded HEVC10 at 3840x2160 and resumed after four absolute seeks.
A D-pad Right command completed a scrub seek, followed by continued playback.
Circle stopped playback. Fresh logs contained no HTTP429 response.
The decoder closed with 626 output frames and `fatal=0` on the second run.
Cumulative seek counters reported ten accepted seeks and zero failures.
Development eboot SHA-256: `563f7b87114da53bafc29fcc6bb32dcaeb7008b74cb629b3408c29f8a30be700`.

The normal alpha.7 build excludes development controls.
The restored player launched with build `9ee9a542-nuvio_1010-0436`.
Fresh feedback confirmed packaged HTTP200 responses and the profile-selection route.
Its eboot SHA-256 is `e800b9ac03f47662bb9452bacb8fe074dc53579c4dc80d6b74c0f641c0985d26`.
Console model: CFI-1016A 01Y. SDK v0.43 and pacbrew v0.39 remained fixed.
Resident exploit, loader, HEN and helper revisions remain unknown.
[TESTED-ON-CONSOLE] The owner reports alpha.7 is installed, tested and working.
The owner approved publication of this build.

## Linux orb setup, 2026-10-30

[LOCALLY BUILT] On a Debian 12 x86-64 Amp orb, `.agents/setup` passed twice.
The first run took 29.94 seconds. The warm run took 16.15 seconds.
The warm run skipped apt and Node downloads. Python was already installed.
Both runs built the browser UI and passed all 60 tests through `make check`.
Documentation and private-artifact checks passed, with one existing passive-voice advisory.

The environment used Python 3.13.7, Node.js 22.23.2 and Debian Clang 14.0.6.
Host FFmpeg libraries were libavformat 59.27.100, libavcodec 59.37.100 and libavutil 57.28.100.
These host libraries do not replace the pinned console FFmpeg libraries.
A minimal-environment `/bin/bash -lc` selected the pinned Python and Node executables.
The login profile contained one toolchain hook after both setup runs.
`.agents/resume` passed in 0.05 seconds without installation or console access.

[UNKNOWN] The native adapter still requires macOS. No native artifact changed.
This session produced no new console execution result or hardware artifact hash.
Future-orb activation requires these scripts on the project's default branch.

## Complete Linux build, 2026-10-30

[LOCALLY BUILT] The complete title and all eight helpers built on Debian 12 x86-64 in a four-core Amp orb.
The host used Python 3.13.7, Node.js 22.23.2, LLVM/Clang/lld 19.1.7, nasm 2.16.01 and host zlib 1.2.13.
SDK v0.43, pacbrew v0.39 and all source revisions and archive checksums remain unchanged.

The original UI-kit download returned HTTP404 before compilation.
The Phononenom mirror reproduced the pinned archive SHA-256, so only its download URL changed.
The builder now selects Linux host tools and static host zlib without Apple SDK paths.
The FFmpeg cache key includes the selected LLVM version.

Build and package commands:

```sh
NUVIO_WORK_DIR="$PWD/build/linux" make build
NUVIO_WORK_DIR="$PWD/build/linux" make release
unzip -t release/PPSA99997.zip
```

The first build took 268.83 seconds, including uncached FFmpeg 7.1.1 compilation.
The second build reused FFmpeg and took 143.71 seconds while setup validation also ran.
Both builds compiled 216 player objects and passed signed-container integrity checks.
The generated runtime matched the existing pinned SHA-256.
The converted title imports `libkernel.prx`, not `libkernel_web.prx`, and has no Linux shared-library imports.
The second receipt covers 237 title files and eight helpers.
Release packaging verified the receipt and helper ELF section headers.
The store ZIP passed `unzip -t`.

| Second-build artifact | SHA-256 |
|---|---|
| `PPSA99997.zip` | `523fa1d226b8b9d00d8fcd8dd1eea570ac0d00ed02a973b3dfd0ca5eb292c5fd` |
| `eboot.bin` | `a8f7b397682fe6451191529a4d6c255608cd97359938912bd763e55334ad9a47` |
| `sce_module/libc.prx` | `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036` |
| Embedded promotion helper | `2f4d1e2a299aa67d9e8b9a04d6ec80f82a92eb11e86378712cac5b52047cecc1` |
| `nuvio.elf` | `777211f13f556cebf4fb1af18e0bbe873179e1947b01c70bcc438e6becdca8e3` |

The final orb setup passed twice in 15.71 and 16.14 seconds with tools and input archives already present.
Both runs verified the five native input archives without downloading or extracting them.
A clean login shell selected LLVM 19 and the pinned Python and Node versions.
Resume passed in 0.04 seconds. All 60 host tests, documentation and source checks passed.
The Linux CI job now builds the complete title and runs release packaging.
Its remote execution remains pending until these changes reach GitHub.

[SOURCE-VERIFIED] A host-side adaptation check preserved the macOS Apple zlib and compiler paths and passed Bash syntax checks.
[UNKNOWN] This session did not rerun a native build on macOS or access a console.
Linux-built startup, UI, playback, seeking and exit still need firmware 13.60 console validation.
The receipt retains `firmware_validation: [UNKNOWN]`. No installation or release publication occurred.

## Firmware 12.70 startup investigation, 2026-10-30

[TESTED-ON-CONSOLE] The owner supplied a native log from a reported firmware 12.70 console.
All four launches identify build `9ee9a542-nuvio_1010-0436`.
Each records `bootstrap: promotion failed stage=transfer errno=92`.
The browser dialog opens, but the page watchdog closes it after approximately 20 seconds.
The log contains no listener-start or page-route events.
The installed eboot hash, console model and resident support-stack versions remain unknown.
The supplied log stays outside Git because it can contain private data.

[SOURCE-VERIFIED] SDK v0.43 defines errno 92 as EPROTO.
The bootstrap reports EPROTO when the connection closes without a verified helper response.
The permission helper explicitly rejects firmware other than 13.60.
[INFERENCE] That restriction explains the reported failure, but this log does not preserve the helper's rejection message.

[LOCALLY BUILT] `scripts/compatibility.c` uses the pinned SDK's process-query example and its 96-byte app-info buffer size.
It reports the firmware value and searches the returned buffer for the exact Nuvio title identity.
It prints match positions without printing raw buffers or unrelated title identities.
It does not change credentials, signal processes, write files or test network permissions.
Its output goes to the loader connection, not `evo.log`.
Existing firmware guards and release packages remain unchanged.

The diagnostic built on Linux x86-64 with Python 3.11.6, LLVM/Clang/lld 19.1.7 and SDK v0.43.
The builder verified the SDK archive against `deps.lock` before extraction into `build/compatibility/sdk/`.
Build and validation commands:

```sh
LLVM_CONFIG=/usr/bin/llvm-config-19 \
  build/compatibility/sdk/ps5-payload-sdk/bin/prospero-clang \
  -std=c11 -O2 -Wall -Wextra -Werror scripts/compatibility.c \
  -lkernel_sys -lkernel_web -o build/compatibility/nuvio-compatibility.elf
python3 scripts/elfcheck.py build/compatibility/nuvio-compatibility.elf
make check
```

Diagnostic SHA-256: `3766b6e3b1e1f08bb38e1d0099d38eba57b28724fed63075e17d416437a63a1c`.
The unstripped ELF has 110888 bytes and 20 section headers.
All 61 host tests, documentation checks and private-artifact checks passed.
Synthetic process responses cover title positions 16, 20 and 86, missing and ambiguous matches, query failure and malformed records.
These tests do not establish the firmware's actual app-info layout.

[UNKNOWN] The diagnostic has not run on firmware 12.70 or 13.60.
No console transfer, installation, settings change or recovery occurred during this preparation.
Next, keep Nuvio open at the splash and capture the diagnostic's loader output using an explicit console address.
Record the console model, support-stack versions and observed output before proposing a permission-helper change.

### Owner diagnostic result and permission-test preparation

[TESTED-ON-CONSOLE] The owner verified the diagnostic's SHA-256 on macOS before sending it through the existing loader.
With Nuvio open, the diagnostic reported `firmware_raw=0x12700001 existing_helper_allows=no`.
It found one `eboot.bin` candidate and one exact Nuvio title match at byte 16 of the 96-byte buffer.
No app-info query failed.
This confirms process identification on that boot, not credential changes or UI compatibility.
Console model and resident jailbreak, loader and HEN versions remain unknown.
The owner supplied the output. This orb did not connect to the console.

The owner used this command, with the private console address omitted:

```sh
nc -w 10 <console-address> 9021 < "$HOME/Downloads/nuvio-compatibility.elf"
```

[LOCALLY BUILT] The opt-in `NUVIO_TEST_FW_1270` build of `scripts/promote.c` permits only firmware 12.70.
The normal helper still permits only 13.60. The watcher firmware check remains unchanged.
The experiment retains exact-title matching, ambiguity refusal and credential readback.
It uses the existing SDK privilege values without new offsets or platform symbols.
It changes the running title's credentials, not installed files or settings.
Those credentials do not survive termination of that title process.

```sh
LLVM_CONFIG=/usr/bin/llvm-config-19 \
  build/compatibility/sdk/ps5-payload-sdk/bin/prospero-clang \
  -std=c11 -O2 -Wall -Wextra -Werror -DNUVIO_TEST_FW_1270 \
  scripts/promote.c -lkernel_sys -lkernel_web \
  -o build/compatibility/nuvio-permission-test-1270.elf
python3 scripts/elfcheck.py --quiet build/compatibility/nuvio-permission-test-1270.elf
make check
```

Permission-test SHA-256: `91e0e2744d144aa6991557bbe7abfdf01ca64ef085f0413c62da3224f6365add`.
The unstripped ELF has 110912 bytes.
Both experimental and normal one-shot helpers compile with SDK v0.43 and LLVM 19.1.7.
All 61 host tests, documentation checks and private-artifact checks pass.
An additional temporary harness passed 18 synthetic firmware and identity cases under GCC 12.2.0 ASan and UBSan.
It covered 12.70, 13.60 and rejected 12.80, plus missing and ambiguous titles.
The initial Clang 19 sanitizer link failed because its host sanitizer libraries were absent.
GCC's installed sanitizer libraries enabled that host-only check without changing the PS5 compiler.

[UNKNOWN] The permission test has no console result. No revised title package installation occurred.
Ask the owner before the credential-changing test. Do not describe it as a read-only diagnostic or a completed fix.
After a verified credential result, prepare and validate a title that starts its listener on firmware 12.70.

### Owner permission-test result

[TESTED-ON-CONSOLE] The owner approved the temporary credential change and verified the permission-test SHA-256 on macOS.
With Nuvio open, the owner sent the recorded `nuvio-permission-test-1270.elf` to the existing loader on port 9021.
The helper found one Nuvio process, reported its previous credentials and returned:

```text
NUVIO promote verified: native network privileges applied
```

The helper reaches that message only after reading back the requested authentication ID and all capability bytes.
This establishes the credential operation on the measured 12.70 boot.
It does not establish listener startup, page loading, playback or a fresh-boot launch.
The owner used `nc -w 10 <console-address> 9021 < "$HOME/Downloads/nuvio-permission-test-1270.elf"`.
The console model, resident support-stack versions and installed eboot hash remain unknown.
No installed title file changed during this test. The owner reported no recovery action.

[SOURCE-VERIFIED] The normal one-shot helper now permits only 12.70 and 13.60.
The 12.70-only experiment remains available to reproduce the recorded permission test.
The legacy watcher and automatic close helper retain their 13.60 restrictions.
The updated embedded helper is the only runtime change in the candidate title.
Tests exercise both permitted firmware versions and reject 12.60, 12.80 and 13.70.
Missing and ambiguous title matches still prevent promotion.

### Firmware 12.70 candidate build and transfer preparation

[LOCALLY BUILT] The complete candidate built with Python 3.13.7, Node.js 22.23.2 and LLVM/Clang/lld 19.1.7 on Linux x86-64.
SDK v0.43, pacbrew v0.39, FFmpeg 7.1.1 and all upstream source pins remain unchanged.

```sh
. .cache/orb-tools/env
NUVIO_WORK_DIR="$PWD/build/firmware-1270" make build
make check
```

Build `9ee9a542-nuvio_1030-2323` passes signed-container integrity inspection with the default authority.
It imports `libkernel.prx`.
The receipt matches all 237 title files and eight helpers.
All 62 host tests, documentation checks and private-artifact checks pass.

| Candidate artifact | SHA-256 |
|---|---|
| Signed `eboot.bin`, 35989476 bytes | `5d1b4ac2e6191ec6e94c594b5cdf8fc2f0132f8fb4273c6757d1882ecbf88511` |
| Embedded helper, 110912 bytes | `0a80005f6d061ccd5218f595235ad46d9e6ec3060268f6d190bd215adb54ab00` |
| Runtime `libc.prx`, unchanged | `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036` |
| Browser bundle, unchanged from alpha.7 | `84109831940e1e21b85bbc5983f12b8098754a9e9fa9adcabcfe4cda0a91d50e` |
| Read-only eboot verifier, 111400 bytes | `6d37a6f414659925bbb8a44218f1f7291afa1266eecfb6a7478fe84572ec87c8` |

The owner explicitly declined a backup and chose reinstallation from ProsperoStore as the recovery plan.
The manual transfer must not invoke the normal backup-creating hash helper.
The optional `NUVIO_VERIFY_ONLY` build of `vendor/control.c` hashes installed and staged eboots without creating backups.
Normal updater builds retain their backup requirement.
Host tests cover both modes with independent SHA-256 expectations, including an absent staged file.
The read-only verifier imports no write or file-creation function other than `open`, which its source uses only with O_RDONLY.
Its source permits only the fixed installed and staged Nuvio eboot paths.

The verifier build uses the normal Nuvio title substitutions from `scripts/build.py` and these compiler flags:

```sh
-std=c11 -O2 -Wall -Wextra -Werror -DNUVIO_CONTROL_ACTION=5 -DNUVIO_VERIFY_ONLY
```

[UNKNOWN] No candidate title or verifier has run on the owner's console yet.
Keep Nuvio closed during transfer. Verify staged and installed raw hashes before launch.
Replace only the signed eboot and preserve `/data/nuvio/`, the runtime and existing browser assets.
Automatic startup, UI, playback, exit and fresh-boot behavior on firmware 12.70 remain pending.
No commit, push, release publication or candidate installation occurred.

[LOCALLY BUILT] A separate supervised browser preview uses a copy of the packaged UI without the PS5 click-redirection script.
HTTP returned 200 and Chromium reached the guest home route with navigation and catalogue data.
The browser preview does not establish console execution. The owner chose to return to the PS5 installation work.

### Owner verification of the staged 12.70 candidate

[TESTED-ON-CONSOLE] The owner uploaded `eboot.bin.nuvio-update` with ps5upload and ran the read-only verifier through the existing ELF loader.
The owner supplied this output:

```text
NUVIO eboot installed bytes=36155940 sha256=e800b9ac03f47662bb9452bacb8fe074dc53579c4dc80d6b74c0f641c0985d26
NUVIO eboot stage bytes=35989476 sha256=5d1b4ac2e6191ec6e94c594b5cdf8fc2f0132f8fb4273c6757d1882ecbf88511
```

The staged size and SHA-256 match the local candidate exactly.
The installed file still has the old hash. Replacement, installed-hash verification and candidate launch remain pending.
This run created no backup, as the owner requested.

### Owner verification after replacing the installed eboot

[TESTED-ON-CONSOLE] The owner reported removing the old eboot and renaming the verified staged candidate to `eboot.bin` with ps5upload.
The owner ran the same read-only verifier again and supplied:

```text
NUVIO eboot installed bytes=35989476 sha256=5d1b4ac2e6191ec6e94c594b5cdf8fc2f0132f8fb4273c6757d1882ecbf88511
NUVIO eboot stage=absent
```

The installed raw size and SHA-256 now match the candidate exactly, and the staged path no longer exists.
This confirms the eboot replacement, not successful execution.
Candidate launch, listener startup, UI, playback, exit and fresh-boot behavior on firmware 12.70 remain pending.

[TESTED-ON-CONSOLE] After the launch instruction, the owner reported seeing customization and new-profile creation screens rather than an existing profile.
This establishes owner-observed UI loading on firmware 12.70 after the eboot replacement.
No launch log or screenshot accompanies this observation.
Account sign-in, existing-profile synchronization, playback, exit and fresh-boot behavior remain unverified.
The cause of the missing expected profile is unknown. Do not infer data loss or a synchronization failure from the setup screen alone.

[TESTED-ON-CONSOLE] The owner then reported that all existing profiles appeared.
This establishes owner-observed profile-list recovery in the same session without a reported new-profile creation.
The cause and duration of the initial delay are unknown.
Profile selection, saved settings, playback, exit and fresh-boot behavior remain pending.

[TESTED-ON-CONSOLE] The owner subsequently reported that playback works on firmware 12.70 with the candidate eboot.
The owner also reported an unwanted mouse icon.
No playback log, media format, duration or cursor screenshot accompanies this observation.
The report establishes successful owner-observed playback, not validation of every format or playback control.
Exit, repeated launches and fresh-boot behavior remain pending.

### SDK-gated candidate for community testing

[LOCALLY BUILT] The next candidate removes Nuvio's firmware allowlists from promotion, the legacy watcher and the close helper.
The unchanged SDK v0.43 rejects unknown firmware before calling `main`.
The helpers require one exact, terminated `PPSA99997` match within the 96-byte app-info buffer.
Promotion and close query the title identity again before acting.
Source pins, runtime, browser assets and title identity remain unchanged.

```sh
. .cache/orb-tools/env
NUVIO_WORK_DIR="$PWD/build/firmware-portable" make build
make check
NUVIO_WORK_DIR="$PWD/build/firmware-portable" make release
```

Build `9ee9a542-nuvio_1030-2356` used Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM/Clang/lld 19.1.7.
The receipt matches all 237 title files and eight unstripped helpers.
Signed-container integrity inspection passed with the default authority and the `libkernel.prx` import.
All 62 host tests, documentation checks and private-artifact checks pass.
Local packaging passed ZIP integrity, SHA-256 and clean source-inventory checks.
CI now retains experimental packages and their checksums for 14 days without publishing a release.

| Candidate artifact | SHA-256 |
|---|---|
| Signed `eboot.bin`, 35989476 bytes | `08272f56a7419a5c699891b0c5e81c7c142e1ee0c4932c7c96d23e44cd7a6295` |
| Embedded promotion helper, 110912 bytes | `0d7979ff8787680f97a992637c700f5301ce3aa4ec74c2a2d491821b3c469f5b` |
| Legacy watcher | `38f3682fee2eaec5bdc3ee69615fd913b58ff7d6b94251292699a77986d7033d` |
| Close helper | `21fe48d5ada6418476203833a707ee6d8683b8e803a1c7592a2029ca943232a1` |

The read-only diagnostic v2 also compiled with the pinned SDK and strict warnings.
Its unstripped ELF has 110888 bytes and SHA-256 `728d5c3e622663828fad80f00c0f671d1473b71d7eece5e5073f6e59e90621bb`.
It reports successful SDK initialization instead of the removed helper allowlist.
It remains a source-only diagnostic, not an extra package required for testers.

Host tests exercise helper behavior after simulated SDK initialization across six firmware values and three title positions.
They reject missing, repeated and unterminated identities, malformed records, failed target queries and identity changes.
These tests do not establish actual SDK initialization or console execution on those versions.

[UNKNOWN] This SDK-gated candidate has no console result, including on 12.70 and 13.60.
The owner has only a 12.70 console and declined further test files.
Their installed, working two-version candidate remains unchanged.
Community testing must establish startup, UI, playback, return and fresh-boot behavior on each reported firmware.
Do not describe this change as universal firmware support.

### Deferred controller requests

The owner requested hiding the browser mouse pointer and using the controller's Options button for the movie Play options menu.
The reported long-press X action did not open that menu on their console.
These requests remain deferred. This firmware change does not modify browser input or appearance.

## Controller navigation candidate, 2026-10-31

[SOURCE-VERIFIED] This work follows the SDK-gated firmware change without changing its helpers, source pins or title identity.
The owner's console runs firmware 12.70 with an active jailbreak, ShadowMount and an ELF loader.
The installed, owner-tested eboot remains `5d1b4ac2e6191ec6e94c594b5cdf8fc2f0132f8fb4273c6757d1882ecbf88511`.
No console connection, installation, firmware update or hardware test occurred during this controller work.
The earlier 13.60 results do not certify this candidate.

### Source audit and fixes

The audit inspected Nuvio revision `25b984f778e4083dc6c2e768fdb5fcf46012e8b7` and EVO revision `9ee9a5420c73b5be448610e5f0a90a29a75592f3`.
It also inspected the pinned SDK declarations and existing native browser and pad paths.
EVO declares `PadButtons::Options` and `PadButtons::Triangle` in `core/include/evo/Common.hpp`.
Its `Application.cpp` already reads the controller through `scePadReadState` before dispatching browser or native input.
The candidate uses those existing press edges, not guessed DOM events or Gamepad indexes.

| Area | Finding and candidate behavior |
|---|---|
| Primary activation | Redirected `.click()` does not cover keyboard-only actions. X now invokes the existing Enter handlers once. |
| Dialogs | Shared dialog buttons lack `.focusable`. Modal focus now takes precedence over the background page. |
| Profile editing | Editor controls use `.profile-overlay-focusable`. The adapter accepts the editor's existing focus instead of requiring `.focusable`. |
| Streams and catalogues | Stream cards and See All cards have Enter handlers without equivalent click handlers. The adapter uses those Enter paths. |
| Discover | Filter handlers reject synthetic clicks. Enter now opens and selects filters through existing screen handlers. |
| Play options | The old native click adapter generated a fixed 60 ms Enter cycle. It could not preserve a physical X hold. |
| Item menus | Native Options counters call existing profile, poster, home, library, hero, season and episode menu methods. |
| Menu fallback | Movie and series details expose a D-pad-reachable Play options button, including the existing Play manually action. |
| Text entry | Inputs retain focus, click and input handling. PS5 settings dialogs let Up and Down reach their action buttons. |
| Native settings | Triangle opens a controller menu. Settings > Playback also exposes Player settings without a pointer. |
| Pointer | CSS requests `cursor:none`. Pointer presses cannot move DOM focus away from the D-pad selection before X activation. |
| Playback | Native playback buttons, stop handling, stream handoff and browser-return code remain unchanged. |

The adapter blocks activation when focus is hidden, disabled, disconnected or unavailable during a modal transition.
The serial controller poll discards stale counters after backgrounding, a failed request or reconnection.
The native endpoint shares the existing title listener and needs no computer-hosted UI.
The original pointer-only Player settings control remains hidden, with its save-and-close handler available to the new actions.

Search and Discover retain their existing route-history Back dispatch.
Their sidebar-specific Back code differs from that dispatch, but D-pad routes to the sidebar remain available.
No unrelated routing redesign forms part of this candidate.

### Host evidence

[LOCALLY BUILT] The host used Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM/Clang/lld 19.1.7.
The complete native title and eight unstripped helpers compiled with SDK v0.43 and pacbrew v0.39.
The clean-room runtime hash remains `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036`.
The embedded permission helper remains `0d7979ff8787680f97a992637c700f5301ce3aa4ec74c2a2d491821b3c469f5b`.

```sh
. .cache/orb-tools/env
make check
NUVIO_WORK_DIR="$PWD/build/controller" make build
NUVIO_WORK_DIR="$PWD/build/controller" make release
unzip -t release/PPSA99997.zip
```

All 63 host tests, documentation checks and private-artifact checks passed.
Input regressions cover one activation, modal precedence, transition blocking, profile fields and stale native counters.
They also cover browsers that ignore legacy numeric fields in `KeyboardEventInit`.
An isolated GCC 12.2.0 host harness compiled the actual native counter and JSON code with address and undefined-behavior sanitizers.
Asymmetric presses and four concurrent writers produced the expected counters without sanitizer errors.
This does not test real `scePadReadState` delivery during system-browser use.

Build `9ee9a542-nuvio_1031-0047` completed with the default authority and the `libkernel.prx` import.
Receipt verification matched all 237 title files and eight unstripped helpers.
Local packaging passed receipt and ZIP integrity checks.
Generated packages remain outside Git.

| Final local candidate artifact | SHA-256 |
|---|---|
| Signed `eboot.bin`, 35989860 bytes | `308f1f0e68b53ee80c096e7dfde95425365dddb4042b765461ccbf3491c34e1f` |
| `webui/app.bundle.js`, 3168000 bytes | `3796dbc329cbe3641c03d2bdc43287232f8d25262a22f8f62ab28ce2a9c794e2` |
| `webui/ps5-input.js` | `5aaf931420da91b1a49f09dfd597adf7e29d1de25683074149d6688a39795c8f` |
| `webui/index.html` | `6198d774053d2eba88ba6021d03a55ef191c45263c0dd648ef0bb1d09359ddc1` |
| `release/PPSA99997.zip` | `547dc446381d6bcd0a3bed25704f9c66cd7bcb9a9f43387c771998fc83cd0b02` |
| `release/nuvio-ps5-0.1.0-alpha.7.zip` | `3742e847dcfd7ca281ceda3e82217cccb3feed31b432008d56861cb82de1a7e2` |

These hashes identify the final local build, not a future CI rebuild with another timestamp.
Earlier local build `9ee9a542-nuvio_1031-0039` had eboot hash `e645592a53ea01cb3bee86f6b2fa6a4f865296f9641e660a2678e5cdad03e3cb`.
The final build supersedes it and preserves numeric Enter compatibility with the former native adapter.
Neither build has console evidence.

Chromium 156 rendered the patched frontend at 1920x1080 and 1280x720 with device scale 2.
A disposable preview exposed screen objects for host fixtures, without changing the packaged production bundle.
Movie, episode, stream and catalogue fixtures intercepted terminal playback or navigation calls to inspect their arguments.
No stream playback result comes from these probes.

| Executed browser check | Observed result |
|---|---|
| Guest onboarding and profiles | Stationary-pointer activation followed D-pad focus. Profile Options opened Edit. |
| Profile editor | The name field acquired DOM focus. Category selection and Save/Cancel remained visible and reachable. |
| Movie details | Play options fit the action row. D-pad selection and a stationary click opened the existing dialog. |
| Play manually | Modal D-pad selection and X reached the existing action with `manualSelection:true` and `startOver:false`. |
| Episode details | Two Down presses reached episode one. The host Options signal opened its existing menu, including Play manually. |
| Episode selection | Right moved to episode two. Stationary X reached the chooser with episode two's ID. |
| Stream selection | Down selected the second of two streams. Stationary X reached `playStream` with the second ID. |
| Catalogue See All | Right selected the second card. Stationary X reached that card's detail action. |
| Discover filters | Stationary X opened Type. Down and X selected Series. |
| Search | Stationary X retained the search field. Host keyboard entry produced `Controller search`. |
| Multiline settings | Down focused Save. Stationary X saved both lines unchanged and closed the dialog. |
| Player settings | The Playback section rendered its new row with visible D-pad focus. |
| Modal dismissal | Escape closed the episode dialog after its exit animation. Focus returned to the original episode. |
| Pointer styling | Computed `cursor` was `none`. Recording used an automation cursor overlay to show pointer movement. |
| Final production bundle | The packaged UI initialized the adapter. Stationary X dismissed App Update without activating the background. |
| Production Home | D-pad movement and stationary X opened a title detail page from Home. |

Screenshots show movie details, Play manually, episode options, profile editing, multiline Save and the native-settings row.
The inspected recording shows real pointer movement, a D-pad focus change and stationary activation of Play options.
Its final frames show modal dismissal starting, not the settled return state.
The separate DOM check above establishes settled dismissal on the host.
Scrollable background content can extend beyond the viewport. The focused modal actions remained visible.

Failed host attempts remain part of this record:

- An initial input mock lacked `classList`. The corrected mock passed.
- A Python quoting error stopped one patching attempt before compilation. The corrected build passed.
- A preview portal selected the wrong port. Browser checks used the working local preview, not that portal.
- The first recording captured an empty browser session. It does not count as UI evidence.
- A 4K recording overflowed its encoder buffer. The replacement 1280x720, scale-2 recording passed inspection.
- The initial profile capture preceded avatar loading. The replacement capture shows the loaded grid.

### Remaining console checks

[UNKNOWN] This controller candidate has not run on the owner's 12.70 console or a 13.60 console.
Host keyboard events and internal Options signals do not establish physical controller behavior.
The existing native reader might not receive Options or Triangle while the system browser owns the pad.
If Options fails, use the visible Play options button and report the failure without assuming a browser keycode.
CSS might not hide the system browser's own pointer overlay.
Synthetic field focus and click might not open the console keyboard.
Search, profile names and settings entry all require separate console checks.
Long-press X remains unsupported by the click bridge. Use Options or the visible Play options action instead.

Keep the working installation and its settings until the candidate passes a controlled test.
Do not overwrite files while Nuvio runs.
Install the complete candidate folder, including `webui/`, rather than replacing only `eboot.bin`.
Keep all persistent console writes under `/data`.
Keep `/data/nuvio/` and account state intact.
The PS5 continues to host the UI after installation.

For the owner, give installation help one action at a time when they return.
Ask for the current console address only if network access becomes necessary.
Do not scan for it.
After installation, check these actions in order and record each observed result:

1. Open Nuvio from the tile.
2. Select a profile with the D-pad and X.
3. Check whether the pointer remains visible.
4. Focus Play on a movie, then press Options once.
5. Select Play manually with the D-pad and X.
6. Repeat through the visible Play options button.
7. Check profiles, sidebar navigation, catalogues, episodes, streams, menus and dialogs.
8. Check Search, profile-name entry and settings fields with the console keyboard.
9. Check Triangle and Settings > Playback > Player settings.
10. Start playback and check the existing pause and seek controls.
11. Press Circle, then check the restored browser page and focus.
12. Repeat playback and perform a fresh launch.

Record failures without clearing account state or changing firmware.
GitHub Host checks completed successfully for controller commit `2a6fec2047feeda88d0f355d6c6713d37aadb777`.
Both `check` and `native-linux` passed in the push and pull-request runs.
These results do not establish console behavior.

## PR prerelease distribution, 2026-10-31

[SOURCE-VERIFIED] The previous workflow uploaded temporary Actions artifacts but did not publish PR builds as GitHub Releases.
The version-tag workflow created draft releases only.
Its packaging command also used the packager's upstream repository default for asset URLs.

The updated Host checks workflow publishes same-repository PR builds after both check jobs pass.
External fork PRs and push-only runs cannot enter the publishing job.
Publication reuses the uploaded packages and checks their SHA-256 values before creating a fixed-commit prerelease.
The tag identifies the tested merge commit. Release notes also identify the PR head.
Reruns preserve existing release files rather than replace timestamp-dependent builds.
PR releases are experimental, not latest, and retain the existing content version.
Versioned draft releases keep their existing process. Both workflows now use the current repository for asset URLs.

[HOST-TESTED] Linux x86-64, Python 3.13.7 and Node.js 22.23.2 passed all 63 tests and `make check`.
Documentation and source-pin checks passed. The existing advisory writing warning remains.
Checksum-verified actionlint 1.7.7 accepted both workflows without findings.
A disposable probe executed the actual workflow shell blocks with mocked packaging and GitHub commands.
It checked PR versus push tags, fork URLs, exact merge targets, prerelease flags and preservation on reruns.
Real checksum verification accepted matching asymmetric fixtures and rejected a corrupted package.
The probe inspected publication dependencies and the same-repository guard. It did not simulate GitHub's permission engine.

The first documentation check rejected a new semicolon and flagged passive wording. The corrected text passed the repeated check.
No native source or console file changed. This workflow-only change required no new local native build.
The earlier controller candidate hashes above remain separate from future CI builds.
Published assets must retain their own `SHA256SUMS`. Local candidate hashes cannot verify a timestamp-dependent CI rebuild.
No console compatibility result comes from workflow validation.

[CI-TESTED] [Run 41187681236](https://github.com/speed-y/nuvio-ps5-homebrew/actions/runs/41187681236) passed host checks, native compilation and release publication.
The configured runner used Ubuntu 24.04, Python 3.13.7, Node.js 22.23.2 and the LLVM 19 packages.
This record omits the exact LLVM package patch version.
The push-only run correctly skipped publication.

[DOWNLOAD-VERIFIED] [Test release pr-1-56ca0a5cf18d](https://github.com/speed-y/nuvio-ps5-homebrew/releases/tag/pr-1-56ca0a5cf18d) is public and marked prerelease.
Its tag resolves to tested merge commit `56ca0a5cf18d9cb3a09e466521621f1fab264fae`.
Its PR head was `748f97ea2522f616f99ff4ba95cb256402db4c30`.
All three downloaded release assets matched the original CI artifacts byte-for-byte.
`sha256sum --check SHA256SUMS` reported both ZIPs OK. Both ZIP CRC checks passed.
The complete package contains integration sources, pinned dependency metadata, notices and `build.json`.

| Downloaded artifact | SHA-256 |
|---|---|
| `PPSA99997.zip` | `241423af643d3ce43fb9232d802418b369f9540c7a209e67e9ac10f006d440d2` |
| `nuvio-ps5-0.1.0-alpha.7.zip` | `f4f73d996b8da2873e55aadc9aec86c0aab8428146e85189215f5a12996da371` |
| Packaged `PPSA99997/eboot.bin`, 35989860 bytes | `31b3d3be29a641291bbae2541e30c66a2436f89945ee8381be6635b2c2e5e495` |

These hashes identify this fixed tag only. Later rebuilds can differ.
[UNKNOWN] This downloaded candidate still needs console validation on 12.70.

### Owner-assisted PR #1 console check

[OWNER-REPORTED] The owner confirmed the downloaded `PPSA99997.zip` hash matches `241423af643d3ce43fb9232d802418b369f9540c7a209e67e9ac10f006d440d2`.
They closed Nuvio, declined an app backup, and reported completing manual app-file replacement through ps5upload on macOS.
The new launch reached Sign in instead of the expected existing profiles.
This is a failed account-restoration check, not proof that the update deleted the online account or previous local state.
We have no on-console measurement of the installed eboot hash for this test.

The owner found `127.0.0.1_4173.json` under `/data/nuvio/webui/`.
The file manager reported 1.11 KB and a recent modification time.
They downloaded a private copy and ran a local, value-free diagnostic on their Mac.
Its reported results were:

- Valid JSON: true.
- Access token present: true.
- Refresh token present: true.
- Anonymous session: true.
- Profiles entry present: false.
- Saved profile count: unavailable because the entry is absent.

No private JSON, token values or account identifiers entered this repository.
[SOURCE-VERIFIED] The pinned SessionStore reads these exact keys without a prefix.
AuthManager bootstrap treats an anonymous session as signed out, even when both tokens exist.
Therefore the current file does not establish a saved account login.
Do not change the anonymous flag to convert this into an authenticated session.

[UNKNOWN] The previous working installation's exact storage file and frontend hashes remain unverified.
The earlier owner report established profile availability and playback during a session, not durable login after a full app restart.
No pre-update storage snapshot is available for comparison.
Missing restoration, an invalidated session and a different storage selection remain unconfirmed explanations.

[OWNER-REPORTED] After signing in, the owner initially still saw only Profile 1.
They described selecting that profile, encountering PIN setup, then reaching the Essential/Advanced experience selection.
After quitting and reopening the app, their actual profiles appeared.
The initial profile presentation failed, but this observation contradicts a conclusion that all account profiles disappeared permanently.
The exact first-login synchronization response and timing remain unknown.
Do not repeat PIN setup or change experience modes to diagnose this.

[SOURCE-VERIFIED] ProfileManager creates the local Profile 1 default when no profiles entry exists.
The authenticated startup decides the initial route from local profiles and cloud lock states, before its background full-profile pull.
This ordering can present defaults before synchronization. It remains a hypothesis for this console observation, not a measured cause.

[OWNER-REPORTED] The arrow appears when changing screens and disappears after pressing any controller button.
Cursor hiding therefore remains incomplete on this console despite the earlier host computed-style check.
The inspected native dialog declarations and SDK sample expose no documented cursor-hiding option.
The dialog's parts/control values and pointed-to webview structures lack cursor semantics in those sources.
No guessed native flag or simulated physical input has been added.
A system-browser overlay remains a hypothesis, not a confirmed identification of the visible arrow.

[OWNER-REPORTED] The Essential/Advanced selection and related setup screens also show mismatched font styling.
The installed PR #1 package does not include the separate PR #3 font-inheritance changes.
Those exact screens still need verification against the font candidate, including rendered inspection.
Options/Triangle delivery, the remaining controller cases and playback remain pending for this console session.

[OWNER-REPORTED] D-pad scrolling appears to move, then focus automatically returns near the screen center.
The owner identified Home with Continue Watching and reported the same behavior with Down.
Single-press versus held-button behavior remains unreported.
[SOURCE-VERIFIED] The installed PS5 bridge guards pointer presses but does not suppress hover events.
Home's mouseover handler can change the focused card. Discover and catalogue mouseenter handlers can change remembered focus.
Home also has a viewport synchronization path that selects a visible card independently of pointer input.
Neither path is a confirmed cause of this console observation. Console event evidence remains pending.

### Continue Watching focus snapback investigation

[HOST-REPRODUCED] Chromium 156 reproduced hover stealing focus after Home scrolls beneath a stationary pointer.
The fixture used the pinned Home renderer, navigation engine, router and current PS5 adapter.
It supplied local catalogue and Continue Watching data instead of an account or remote addons.
It did not mock focus, scrolling, hover events or directional navigation.

With the pointer at CSS coordinates 850,155, three Right presses followed by two Down presses selected an earlier row after scrolling.
The event trace recorded mouseover changing focus after directional navigation selected the lower row.
One replay selected row 1, column 2 instead of row 2, column 0.
The recorded replay lost progress during scrolling and ended on row 1, column 0.
With the pointer outside the cards at 10,10, the unchanged code retained row 2, column 0.
This isolates a host hover failure without establishing PS5 event delivery.

[HOST-TESTED] The local change captures hover entry and movement events in the PS5-only input script before screen handlers run.
It leaves pointer presses, clicks, keyboard events and native playback unchanged.
The identical host sequence retained row 2, column 0 with one visible focus indicator.
Eight Right presses retained Continue Watching column 8 in Classic, Modern and Grid layouts.
Two subsequent Down presses retained row 2, column 0 in each layout.
The pointer-outside-cards control produced the same result before and after the change.
The controller menu still opened. Down selected Cancel, and a stationary primary click dismissed it and restored Home focus.
Existing input checks still cover modal precedence, text-field activation and stale native button counters.
The extended input regression failed before the change with `mouseover replaced controller focus`, then passed.

The inspected before/after screenshots and recordings show the actual Home UI with fixture titles and placeholder artwork.
The final captures use 1280x720 CSS pixels and device scale 2.
The recording draws an automation pointer overlay to show its position despite CSS hiding.
An initial baseline recording captured an empty page after a browser-session configuration change.
That recording does not count as evidence. Consistent session settings and repeated viewport setup corrected the capture.

[UNKNOWN] The focus change has no console result and does not fix the system pointer's reported appearance during transitions.
The owner requested local artifact testing before any push and prioritized login/profile restoration before another installation.
No new commit, push, PR update, release publication or console file replacement occurred during this investigation.

### First-open account profiles and experience routing

[OWNER-REPORTED] A full restart of the currently installed candidate shows the actual profiles without another sign-in.
The owner identified the failure as first open after installation, not every ordinary restart.
This establishes current session restoration, not preservation across another installation.
The previous anonymous storage snapshot still does not establish a saved authenticated session before replacement.

[HOST-REPRODUCED] A disposable backend substitute supplied a synthetic valid session, two named profiles and a saved Advanced mode.
The production bundle showed Profile 1 without requesting `sync_pull_profiles` on its initial profile-picker path.
In the single-profile case, startup routed to Essential/Advanced before background sync restored the saved mode.
The later profile/settings data did not correct that already-mounted setup screen.
These runs reproduce the reported presentation problems without accessing the owner's account.
They do not reproduce loss of credentials across a console installation.

[SOURCE-VERIFIED] The PS5 adaptation now awaits the existing profile pull before the initial profile decision.
Verified playback returns retain their earlier profile-resume path without this additional wait.
Both experience-route callers already await the result.
The route resolver now awaits the existing settings pull when an authenticated PS5 profile has no local mode or chosen layout.
Existing local choices and guest setup retain their earlier behavior.
Session tokens, native storage restore/save code and console storage paths remain unchanged.
Cloud request failures still follow the existing service fallback. This change adds no sign-out or local-data reset.

[HOST-TESTED] The changed production bundle showed Alex and Sam on the first profile screen instead of Profile 1.
The saved Advanced fixture reached Home rather than Essential/Advanced.
Selecting the second profile with Right and a stationary primary click reached Home with active profile 2.
A restart retained the synthetic session and profile.
A rejected profile pull (HTTP400) retained the cached profile, saved mode and session.
A new account without saved settings still reached experience selection.
A guest still reached profile selection without a cloud profile pull.
The host backend supplied no catalogues, so Home contained its navigation rail and an empty content area.
This does not establish real account-server responses, native storage persistence or console input delivery.

Final profile and mode screenshots use the packaged index, styles and bundles with only the host backend substitute added.
The captures use Chromium 156 at 1280x720 CSS pixels and device scale 2.
An initial fixture lacked translation resources and failed before startup. Adding the packaged resource directory corrected it.
One comparison reused the old cached script after switching a symlink. That run does not count as changed-code evidence.
Distinct script URLs identified by bundle hashes corrected the final before/after comparison.
An unrelated heading/subtitle overlap appears in both profile renders. This investigation leaves that layout unchanged.

[LOCALLY BUILT] The combined focus/profile candidate built on Linux x86-64 with Python 3.13.7, Node.js 22.23.2 and LLVM 19.1.7.
SDK v0.43, pacbrew v0.39, source pins, runtime and title identity remain unchanged.
Build `9ee9a542-nuvio_1031-1013` passed native compilation and receipt verification.
All 63 host tests and `make check` passed. The store ZIP passed its CRC check.

```sh
. .cache/orb-tools/env
make check
NUVIO_WORK_DIR="$PWD/build/controller" make build
NUVIO_WORK_DIR="$PWD/build/controller" make release
unzip -t release/PPSA99997.zip
```

| Combined local artifact | SHA-256 |
|---|---|
| `PPSA99997.zip` | `dba30a8eb1b86b3ad288ccdcd0e90127ea7f5c9932829e935f60c2109ab642f6` |
| Signed `eboot.bin` | `29bd39e0a463cbb9fc4d68173a00d77557179fcb96d9d632d1154a32e8244ad4` |
| `webui/app.bundle.js` | `e1c90c616e809251f153cdc8393a4fc740155e2a56eff4e75bb7698ccbaa2b66` |
| `webui/ps5-input.js` | `d4587a4be7a1830405ab02872e2b6248887a664bd04f61b95463eba44dd57624` |

An earlier focus-only package included disposable browser fixtures during the local build.
That package was rejected and removed before delivery. The clean rebuild and combined package exclude all fixtures.
[OWNER-REPORTED] During the combined candidate test, the owner confirmed that profiles and navigation now work correctly.
The installed hashes remain unmeasured on the console. The candidate excludes the separate playback-loop and font PRs.
The owner requested private local artifact testing before a push. No GitHub publication or merge occurred.
Preserve `/data/nuvio/` during testing. Replace only the app under `/data/homebrew/PPSA99997/` while Nuvio is closed.

[OWNER-REPORTED] The pointer still appears until a controller button press. Physical Options still does not open item actions.
With first-link autoplay enabled, the owner cannot reach the manual-play fallback through stream selection before playback starts.
The owner accepts Square as an alternative actions button. Its browser event representation remains unknown.
The existing native hook logs bounded keydown diagnostics. A console button check must establish delivery before adding a Square mapping.

[SOURCE-VERIFIED] Continue Watching opens details with automatic stream selection instead of presenting its actions menu.
Its menu hides Play manually unless `showContinueWatchingManualPlayOption` is true. No assignment to that property exists in the pinned frontend.
The stream resume path can select a progress identity despite `manualSelection`, which only disables stored-link reuse in that path.
These findings identify source gaps, not measured causes of physical Options failure on the console.

[SUPERSEDED EXPERIMENT] An initial local experiment offered pre-play actions through X. The experiment ended before delivery.
X retains ordinary activation. The observed Square and Options events now open the existing actions menus.
Local changes expose manual play independently of the menu flag and bypass progress-identity reuse during explicit PS5 manual selection.
The installed candidate does not contain these new changes. Console menu behavior and pointer suppression remain unverified.
No new commit or push occurred.

### Square button diagnostic, 2026-10-31

[OWNER-REPORTED] Square caused no visible action during the requested Home button check.
[LOG-OBSERVED] The supplied private log contains 1,506 lines spanning four native sessions.
All four session headers identify build `9ee9a542-nuvio_1010-0436`.
It contains no page key, click, native Options or native Triangle diagnostics.
Even the Up/Down control presses have no recorded key events, so silence does not establish that Square emits nothing.
All four sessions also record a page-watchdog event. These observations do not establish the latest candidate's behavior.

[LOCALLY VERIFIED] The provided local ZIP still hashes to `dba30a8eb1b86b3ad288ccdcd0e90127ea7f5c9932829e935f60c2109ab642f6`.
Its signed eboot hashes to `29bd39e0a463cbb9fc4d68173a00d77557179fcb96d9d632d1154a32e8244ad4` and contains build marker `9ee9a542-nuvio_1031-1013`.
[UNKNOWN] A stale log, an older running executable or incomplete app replacement could explain the marker mismatch.
The current installed executable remains unmeasured. Obtain a fresh session record before assigning Square or diagnosing native button delivery.
The private log stays outside the repository. No account state or playback URLs enter this record.

### Observed browser buttons and manual selection, 2026-10-31

[OWNER-REPORTED] A fresh session identifies build `9ee9a542-nuvio_1031-1013`.
The requested Up, Square, Down, Options sequence produced ArrowUp/38, F2/113, ArrowDown/40, F3/114.
This establishes browser delivery for the tested buttons. It does not establish native counter delivery or other button mappings.

[SOURCE-VERIFIED] The PS5 adapter now handles F2/F3 before the frontend's normal key dispatcher.
Both open existing item menus. Repeated keydown events cannot reopen a menu.
Modal dialogs cannot activate a background item. Editable fields do not open an item menu.
Continue Watching exposes its existing Play manually action on PS5.
Explicit manual selection now also bypasses the remembered progress stream identity.

[HOST-REPRODUCED] A disposable fixture uses the actual Router, FocusEngine, Home, Detail, Stream and dialog implementations.
Synthetic metadata and stream responses replace unavailable owner data. A recording boundary replaces native playback.
Before the fix, F2 and F3 opened no menu. Explicit manual selection still launched remembered source 2 at 1,500,000 ms.
After the fix, both keys open existing movie actions. Episode actions also expose Play manually.
Manual selection stays on the stream screen with two sources and zero launches.
Selecting source 2 deliberately then reaches the playback boundary at the saved position.
The nonmanual control still selects remembered source 2 automatically.
These results do not establish PS5 browser button handling, addon responses, native playback or console return behavior.

[RENDER-INSPECTED] Chromium 156 renders the Continue Watching menu and manual stream screen at 1280x720, scale 2.
Screenshots and a frame-by-frame contact sheet show readable menus, visible focus and two stream choices without clipping.
The recording includes real pointer movement across neighboring cards, menu opening and intentional stream activation.
Its visible pointer is the recorder overlay, not evidence about PS5 cursor suppression.
An initial browser wait used the nonexistent `.stream-card` selector and timed out.
The corrected run waits for `[data-action="playStream"]` and reaches the expected stream screen.

[LOCALLY BUILT] Build `9ee9a542-nuvio_1031-1056` completed native compilation with the previously recorded Linux tools and source pins.
Its signed eboot hashes to `343a0c25e2e654d303c2f6352af08dc2e20338cc81793883653c4f3002afb4c6`.
Its UI bundle hashes to `87e6da33b0483f6e391b8b134149cb9e9840f154830509f9dc19183f95655b7e`.
This build has no console test or delivered package. A replacement release ZIP remains pending.

### Collection artwork-only screen and metadata configuration

[OWNER-REPORTED] Home collection folders open to their artwork without catalogue contents.
The before/after photos show New Movies, not an individual movie detail screen.
The owner also reports missing Creator and Cast information.

[ARTIFACT-VERIFIED] The local ZIP identified above as `dba30a8e...` contains no TMDB API key or Trakt client ID.
The build configuration copies login and avatar settings from the pinned official release, but excludes these metadata settings.
The pinned official runtime configuration contains both values. These checks printed only presence, not the values.

[SOURCE-VERIFIED] TMDB collection sources require an API key and enabled TMDB integration.
TMDB cast enrichment also requires that key and the enabled integration setting.
Addon-provided cast metadata can still populate the cast section independently.
In Modern/Follow Layout folders, failed or empty rows disappear while the collection artwork remains.
Thus the missing key blocks TMDB-backed features, but does not establish the cause for an addon-backed collection.

[UNKNOWN] The owner's folder source types, integration settings and request outcomes remain unmeasured.
This audit requested or copied no owner account data, addon URLs or credentials.
No metadata configuration change, console replacement, push or PR update occurred during this audit.

### Private controller and metadata candidate, 2026-10-31

[SOURCE-VERIFIED] The runtime configuration whitelist now includes the pinned official browser package's TMDB API key and Trakt client ID.
The existing anonymous Supabase key check remains unchanged. URL fields still require HTTPS.
The build does not copy unrelated client credentials or change profile settings.
The configuration regression failed on the previous implementation because `TMDB_API_KEY` stayed empty.
It passes after the fix and checks that an unrelated credential stays absent.

[HOST-REPRODUCED] A disposable folder fixture uses the real Router, FocusEngine, collection store, folder renderer and source loader.
Both comparison runs enable TMDB and use the same synthetic Modern/Follow Layout folder with one TMDB discover source.
The old packaged configuration produces `TMDB is not configured`, zero cards, no focused card and only collection artwork.
The changed packaged configuration receives HTTP200 from TMDB and displays 20 movie cards in one row with visible focus.
The first result's enrichment returns 36 cast entries and 27 crew entries.
Opening that result through ordinary focused activation renders details and three visible actor cards.
D-pad navigation reaches the first actor card, Robert Downey Jr., with visible focus.
This uses public TMDB responses, not substituted metadata or the owner's catalogue configuration.
The native browser, console network and owner's folder sources remain untested.

[HOST-CONTROL] Disabling TMDB still prevents source loading despite the configured key.
The package does not silently enable the integration or change the owner's choice.
The owner must check the profile's TMDB integration setting if a TMDB-backed folder stays empty.

[FAILED HOST CHECK] Trakt's public trending request fails in Chromium with a fetch TypeError.
A host HTTP request receives HTTP403, a Cloudflare server header and no access-control allow-origin header.
A second request without the Origin header also returns HTTP403 with a plain-text response.
These observations do not establish whether the client ID, provider policy or orb network caused the failure.
The package contains the client ID, but functional Trakt catalogue access remains unverified.

[RENDER-INSPECTED] Final collection and cast captures use Chromium 156, a 1920x1080 CSS viewport and scale 2.
The populated collection shows loaded posters, an expanded focused card and readable row labels.
The details capture shows actor names, portraits, directors and focused cast navigation.
An initial fixture missed relative translation resources and failed before mounting. That run does not count as product evidence.
A later incorrect detail-root wait timed out although the route completed. The corrected check waits for cast cards.
An early 1280x720 collection capture clipped the row heading. Final captures use the console-sized viewport after expansion settles.
No layout changes attempt to fix that smaller-viewport presentation.

[LOCALLY BUILT] Build `9ee9a542-nuvio_1031-1106` completed native compilation and receipt-checked release packaging.
The host uses Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM 19.1.7.
SDK v0.43, pacbrew v0.39, firmware handling, source pins and title identity remain unchanged.
`make check` passes 64 host tests. The store ZIP passes its CRC check.
The ZIP contains 237 files and no disposable browser fixtures.
Its login and avatar configuration exactly matches the previous private candidate.
Only `TMDB_API_KEY` and `TRAKT_CLIENT_ID` differ in the runtime configuration.

| Private candidate artifact | SHA-256 |
|---|---|
| `PPSA99997.zip` | `5977a6d3343afbdc1f6d416f221498f2a7abe9520fe1726031d0e5a948e71589` |
| Signed `eboot.bin` | `df659ed39696606a60c3831e008d32d85c6f81a2414dba823c3fdfd0fed50ea1` |
| `webui/app.bundle.js` | `87e6da33b0483f6e391b8b134149cb9e9840f154830509f9dc19183f95655b7e` |
| `webui/nuvio.env.js` | `cd060e4a6416592cd738f52dd47327191639d2e1316aa3447e4ce0dc26ab5bc7` |

[PENDING CONSOLE TEST] This candidate includes profile restoration, hover-focus suppression, observed F2/F3 actions and manual-selection changes.
It excludes the separate playback-return-loop and font-inheritance PRs.
The pointer's reported appearance before a button press remains unresolved.
No new commit, push, PR update, GitHub release publication or console file replacement occurred.
Close Nuvio before replacement. Preserve `/data/nuvio/` and replace only the app folder under `/data/homebrew/PPSA99997/`.

### Owner follow-up: Options works, playback and account state fail

[OWNER-REPORTED] After opening the latest private candidate, the owner confirms that the physical Options button opens the menu.
A playback attempt then failed for an unknown reason. Catalogue content gradually disappeared.
The next app launch requested sign-in again.
The installed build marker and hashes for this session remain unmeasured.
These failures mean the candidate is not ready for publication despite its passing host checks.

[SOURCE-VERIFIED] The frontend's explicit account teardown removes session tokens, profiles, addons and profile-scoped settings.
An invalid refresh response or an unresolved authenticated 401 can reach that path.
The native hook separately restores and saves browser storage through `/evo/storage`.
Neither source path establishes which event occurred during this failure.
A fresh console log must distinguish playback handoff, browser reopening, script failure and storage activity before further changes.
No session-reset workaround, speculative authentication change or replacement candidate accompanies this report.

[OWNER-REPORTED] The PS5 home-screen tile uses a generic controller/grid icon. This predates the current changes.
[ARTIFACT-VERIFIED] The private ZIP includes `sce_sys/icon0.png`, a 512x512 Nuvio-branded image matching `assets/icon.png` exactly.
Its SHA-256 is `d5a3f3d4288081e055cd1013e61f61d2e8ac4af80172cd3c30da1cbf7b4cb3c4`.
This establishes the packaged artwork, not the installed icon or ShadowMount's registered home-screen metadata.
The cause of the generic tile remains unknown and separate from the playback/account investigation.

### Owner follow-up: missing catalogue posters, 2026-10-31

[OWNER-REPORTED] Signing in again shows the correct profiles without the earlier first-open profile problem.
Posters appear after opening a title and returning. Netflix and HBO folders load, but have missing posters.
New Movies and New Series collection folders still show only their artwork.
The installed marker and hashes remain unmeasured. This report does not establish reliable session persistence.

[PHOTO-INSPECTED] The supplied Home photo shows New Series and Popular Series rows, not an empty collection folder.
Two New Series posters render. Other cards remain dark, including cards with watched badges.
The selected title's hero artwork and metadata render. The photo establishes missing artwork, not missing catalogue entries.

[SOURCE-VERIFIED] Initial Home rows use poster images with `src` and `loading="lazy"`.
The explicit Home hydration index selects only images with `data-src`, so those initial images bypass that hydration path.
Focused-poster promotion separately requests eager loading when the configured expansion flow runs.
This difference suggests a loading hypothesis. It does not establish the PS5 failure's cause or exclude failed image requests.

[HOST-CONTROL] The unchanged private UI loads public default catalogues in Chromium 156 at 1920x1080, scale 2.
The Modern Home DOM contains 80 poster images: 50 loaded, 30 intentionally deferred, zero failed and zero pending nondeferred images.
Public Metahub small and medium poster requests also return HTTP200 with image content.
Separate Python requests for Cinemeta's series top and year catalogues return HTTP403.
The browser nevertheless loads default catalogue rows. These differing results do not establish the console's network behavior.
These checks use no owner account, addon URLs or private browser state.

[HOST-CHECKED] Loading `.cache/orb-tools/env` before `make check` passes all 64 tests and the documentation and source checks.
The initial run without that environment fails the compatibility harness compilation at `scripts/promote.c:85`.
GCC treats misleading indentation as an error. No source change separates the failing and passing runs.
This unrelated compiler-dependent check remains unchanged and has a separate fix suggestion.

[PENDING CONSOLE CHECK] Highlight a previously unopened blank poster with the D-pad and wait without pressing X.
Determine whether focus alone loads its image before changing the image-loading policy.
Folder provider configuration and fresh playback/session diagnostics remain unknown.
No thumbnail code change, replacement artifact, commit or push accompanies this investigation.

### Owner follow-up: sidebar absent after playback, 2026-10-31

[OWNER-REPORTED] A video played and returned to a title/episode screen showing Next S1E1 and play options.
The controls still responded, but the owner found no usable path back to browsing.
The owner force-closed and reopened Nuvio to recover.
[CLARIFIED BY OWNER] The owner searched for the Home/Search sidebar and did not try Back.
The earlier classification as a pending back-navigation defect was premature. No failed Back action has been reported.

[SOURCE-VERIFIED] The pinned movie and series detail layouts do not render the Home/Search sidebar.
Their keyboard handler processes Back through detail-state handling, then `Router.back()`.
Sidebar absence on these layouts alone does not establish a defect.

[UNKNOWN] Actual Back behavior after this console playback return remains untested.
The exact route, return history and installed build marker remain unmeasured.
Keep Back after playback as a validation check, not a confirmed failure or an assumed successful path.
The owner will finish the pending poster check first. No additional console test or file replacement accompanies this report.

### Focused-poster check and private image diagnostics, 2026-10-31

[OWNER-REPORTED] Highlighting a blank title for ten seconds leaves its poster blank, while its background artwork loads.
This completes the requested waiting check. Waiting on focus is not a workaround on the tested console.
The result does not establish whether the poster request failed, remained deferred or loaded without visible rendering.

[SOURCE-VERIFIED] Focused Home metadata enrichment can update background artwork independently of the existing poster element.
A loaded background therefore does not establish poster delivery or decoding.
The adapter now records poster-state counts through the existing native `/evo/log` endpoint.
It records at most six samples, at least ten seconds apart, only on Home or collection-folder routes.
It records the focused poster's state, coarse provider category, lazy attribute, nonzero box and positive opacity.
It also decodes one locally generated 2x3 lossy WebP sample without a network image request.
No image URLs, titles, addon addresses, account state or arbitrary error text enter these diagnostic messages.
No native hook means no diagnostic requests. Diagnostics do not alter image sources, loading policy, focus or account storage.
The existing native log can still contain private data outside these messages. Do not share its raw contents without review.

[HOST-VERIFIED] A disposable Chromium 156 fixture uses the actual adapter with a route stub, DOM images and local HTTP responses.
The fixture contains two loaded images, three undecodable responses, one pending request, one deferred image, one missing source and one placeholder.
All six summaries report those exact counts. The focused image reports failed, lazy, a nonzero box and positive opacity.
The generated WebP decodes at the expected dimensions. The endpoint receives exactly thirteen bounded messages, including the format result.
The same page without the native hook sends no additional diagnostics.
No message includes the fixture URL token, title or an HTTP URL. Every message stays below the native endpoint's 200-character diagnostic limit.
These checks validate diagnostic classification and redaction, not the PS5 failure's cause.
The initial navigation command times out because the fixture deliberately holds an image response open.
The URL and subsequent DOM/endpoint checks confirm that the fixture and adapter ran despite that timeout.
The disposable fixture, browser session and service were removed after validation.

[LOCALLY BUILT] Build `9ee9a542-nuvio_1031-1141` completes native compilation and receipt-checked release packaging.
The tools remain Linux x86-64, Python 3.13.7, Node.js 22.23.2, LLVM 19.1.7, SDK v0.43 and pacbrew v0.39.
The store ZIP passes its CRC check. Relative to the 1106 private ZIP, only the eboot and UI bundle differ.
Configuration, assets and the early input shim remain byte-for-byte unchanged.

| Private diagnostic artifact | SHA-256 |
|---|---|
| `PPSA99997.zip` | `78ac410e6adc72185b2d8ead00aa5df851a1b64f922267b025a605cbed14d1a6` |
| Signed `eboot.bin` | `53888b4fd993c1363045e02e48772e0771009933c814746b577178ccb2ffcc69` |
| `webui/app.bundle.js` | `75224c50300aa7238ab9de95ba5a9a8875552166ebada6e673af56412bfa1956` |

[PENDING CONSOLE TEST] The diagnostic UI bundle can replace only `webui/app.bundle.js` while Nuvio is closed.
This UI-only test retains the installed eboot and its build marker. Identify the UI by its bundle hash.
Preserve `/data/nuvio/`. No account-state replacement or new sign-in is part of the test procedure.
This candidate diagnoses the thumbnail failure but does not claim to fix it.
No new commit, push, PR update or GitHub publication occurred. The remaining catalogue and session failures remain unresolved.

### Owner image diagnostic results, 2026-10-31

[OWNER-SUPPLIED CONSOLE DIAGNOSTICS] The owner reports one Home sample followed by five identical collection-folder samples on firmware 12.70.
The test follows replacement of the diagnostic UI bundle described above. Its installed hash remains unmeasured.
The native eboot was not part of that UI-only replacement.

| Route | Loaded | Failed | Pending | Deferred | Missing source | Non-image placeholder |
|---|---:|---:|---:|---:|---:|---:|
| Home, one sample | 17 | 0 | 229 | 116 | 0 | 0 |
| Collection folder, each of five samples | 0 | 0 | 0 | 0 | 0 | 1016 |

The focused Home poster reports loaded, provider other, lazy loading, a nonzero box and positive opacity.
The focused folder poster reports placeholder, provider none, no lazy attribute, a nonzero box and positive opacity.
The inline WebP probe reports successful decoding. This does not establish support for every remote WebP image.

[SOURCE-VERIFIED] The diagnostic classifies non-HTMLImageElement matches as placeholders, not as failed image requests.
The card renderer creates a placeholder div for loading items or an empty selected poster source.
The folder requests the Modern layout without poster labels, and its source rows suppress poster text.
Consequently, cards without artwork can be difficult to distinguish from an empty folder.
These source paths do not establish which condition produced the owner's 1016 matches.

[OWNER-CLARIFIED] The five collection-folder samples came from HBO Max, not New Movies or New Series.
[SOURCE-VERIFIED] Saved sources take precedence over streaming-network fallback sources.
The HBO Max name alone therefore does not identify its provider.
[UNKNOWN] The sampled folder's source providers and loading/item state remain unknown.
The Home sample does not measure changes over time or a focused blank image.
Native lazy images can remain pending before their requests start. These counts alone do not establish a request storm or network failure.
Do not diagnose a missing key, change image formats or force all images to load from these results alone.
The New Movies and New Series failures still need separate diagnostic evidence.
No runtime change, replacement candidate, commit or push accompanies these results.

### Catalogue reorder labels, 2026-10-31

[PHOTO-INSPECTED] The owner's Reorder Home Catalogs screen has narrowly wrapped names and a wide, blank focused control.
Visible entries include a four-folder Trending / New collection, Calendar videos from AIOMetadata, and a sixteen-folder Streaming Services collection.
The photo identifies collection rows separately from addon rows. It does not identify the sources saved inside the HBO Max folder.

[SOURCE-VERIFIED] The two reorder buttons contain Material Icons ligature strings and depend on the remote Google icon stylesheet and font.
The PS5 adapter now uses visible Move up and Move down text, with explicit accessible labels.
Other platforms retain their existing icons. No change affects catalogue order, source configuration, image loading or account storage.
The guarded source replacements regenerate through the normal UI build and appear in `patches/nuvio.patch`.

[HOST-REPRODUCED] A disposable fixture renders the actual pinned screen with remote fonts blocked and synthetic rows.
The original arrow controls occupy 358 and 421 CSS pixels. At 1280x720, the first name column shrinks to about 21 pixels.
The changed controls occupy 168 and 208 pixels, and the name column measures about 425 pixels.
This reproduces a missing-font layout failure. It does not establish the cause of the console's blank icons.

[HOST-VERIFIED] Chromium 156 keyboard checks move one row per activation and preserve focus on the moved item.
First-row and last-row navigation skip unavailable movement actions. Disable changes to Enable, and Enable restores the preference.
The fixture uses the actual early input shim and navigation adapter. Its Back stub receives one request.
The non-PS5 control retains all eight original icon elements across four fixture rows.
[RENDER-INSPECTED] Captures at 1920x1080 and 1280x720, scale 2, show readable labels without title/control overlap.
The disabled-row capture shows Disabled on Home and focused Enable. The 1280-pixel layout has no horizontal overflow.
These host checks do not establish real PS5 button delivery or the installed screen's appearance.

[FAILED CAPTURE ATTEMPTS] A recording context switch produced a blank page, and a subsequent clip missed transient asynchronous updates.
A retry waited for visible state changes but failed because the recording encoder fell behind.
Those clips are not validation evidence or delivered artifacts. Inspected screenshots and executed DOM checks remain the available host evidence.

[LOCALLY BUILT] `NUVIO_WORK_DIR="$PWD/build/controller" make ui` completes with the configured orb tools.
The host tools remain Python 3.13.7 and Node.js 22.23.2 on Linux x86-64.
The UI bundle SHA-256 is `90a95a0db084d96a7ca864aac28a2590af0b053c22bebfaf208e8e3475e5fc53`.
The stylesheet SHA-256 is `88280017833dfe1ac395c76151a4647c92a0f91c27f0d9dfbcf33ac7c1089363`.
No native source changed in this edit batch, and no native rebuild or new eboot marker accompanies the UI-only candidate.

[PENDING CONSOLE TEST] The label fix needs validation on the owner's 12.70 console before publication.
Close Nuvio before replacing only `webui/app.bundle.js`. Preserve `/data/nuvio/` and all catalogue preferences.
Missing posters, empty folders, pointer presentation and session reliability remain separate unresolved issues.
No new commit, push, PR update or console replacement occurred.

[OWNER FOLLOW-UP] The owner downloaded the UI-only candidate, closed Nuvio, and reported replacing `webui/app.bundle.js`.
After reopening Reorder Home Catalogs, the owner reports that it looks good.
This confirms the reported appearance on 12.70, not an installed hash or successful reorder activation.
The installed bundle hash remains unmeasured. No sign-in or catalogue-order change was part of this test.

[NEXT INVESTIGATION] The owner does not know where the collections originated and requests inspection of saved configuration instead.
The inspected native storage snapshot maps localStorage keys to JSON-encoded strings.
Collection sources live under `collectionsState`, potentially inside a profile-scoped envelope.
The full browser snapshot can contain session tokens and private addon addresses. Do not request a raw public upload.
Use a fresh, read-only local copy and extract only whitelisted catalogue settings before sharing diagnostic output.

[HOST-VERIFIED] A disposable Python extractor reads the newest matching snapshot from the owner's Downloads directory without modifying it.
Its output contains selected-profile collection structure, known folder labels, source enums, identifier-presence checks and four TMDB boolean settings.
Unknown titles become numbered aliases. Raw IDs, profile IDs, addon addresses, tokens and arbitrary setting values are not output fields.
Synthetic tests cover JSON-encoded profile envelopes, active-profile selection, legacy arrays, decoded objects and absent state.
Sentinel credentials, URLs, unknown titles and invalid enum strings do not appear in output. Input bytes remain unchanged.
The tested extractor is a private review artifact, not a new committed runtime dependency.
The owner reports downloading the fresh console snapshot. Its contents have not yet been inspected or shared.

[OWNER-SUPPLIED SUMMARY] The extractor reports no selected-profile collection entry and an empty collection list.
Its TMDB enabled, modernHomeEnabled, useArtwork and useCredits flags all report true.
This distinguishes the observed snapshot from the disabled-TMDB host control. It does not establish live API access or a configured runtime key.
The extractor result does not distinguish an absent root key from an absent selected-profile entry.

[SOURCE-VERIFIED] The native snapshot excludes every localStorage value longer than 524288 JavaScript characters, regardless of its key.
The native saved-body limit is 8 MiB. Collection settings can contain artwork URLs, but their actual size remains unmeasured.
Do not attribute the missing configuration to this exclusion without evidence from the failing case.
The owner requests direct inspection instead of further relayed commands. A connected Mac runner permits read-only inspection of the downloaded snapshots.
Keep authentication data and private addon addresses on the Mac. Return only sanitized findings to the investigation.

### Direct snapshot inspection and live collection diagnostics, 2026-10-31

[READ-ONLY MAC INSPECTION] One matching downloaded snapshot exists. Its size is 871690 bytes and its modification time is 13:08:55 Europe/Budapest.
The root contains 45 JSON-encoded storage strings. The exact `collectionsState` key is absent, not an encoded null.
Recursive decoding finds no collection or folder definitions. No duplicate file or selected-profile lookup explains the missing entry.
TMDB settings, Home catalogue preferences and installed-addon settings contain the selected profile.
The four reported TMDB flags are true. The cached addon manifest string contains 103621 characters.
No New Movies, New Series, HBO Max or Netflix source definition can be verified from this file.

The largest included value contains 405853 JavaScript UTF-16 characters. Included values total 811975 characters, each below the 524288-character threshold.
These measurements do not establish the missing live value's size or prove exporter omission.
No Mac file changed. The inspection made no network request, console connection or account login.
No private config, token, URL or profile identifier entered the repository.

[SOURCE CHANGE] The existing bounded UI diagnostic now measures live `collectionsState` presence, character count and threshold comparison.
Collection-folder samples also count source providers, loading/error states, items without artwork and items marked as loading.
Known target folders use fixed labels. Unknown folder names and source providers become other.
The diagnostic does not log storage contents, source IDs, URLs or error text. It does not change storage, loading policy or focus.
The existing native hook guard, six-sample limit and ten-second interval remain in effect.

[HOST-VERIFIED] The actual adapter passes controlled absent, empty, exactly 524288-character and 524289-character cases.
An astral-Unicode case verifies JavaScript UTF-16 length at the exact boundary.
Asymmetric tab fixtures verify provider totals, loading/error counts, artwork fallback fields and exclusion of the combined All tab.
The fixture reports six items, two without artwork and one marked as loading.
Unknown names, providers, source addresses and error strings remain absent from messages.
Every message stays below 200 characters. Sampling stops after six reports, and no native hook means no diagnostic requests.
These host checks validate the observation mechanism, not the collection omission or poster failure on PS5.
An artwork-only folder fixture with zero poster elements also reports its empty source state and live storage measurement.
Home still skips samples without poster elements. This prevents blank folder screens from suppressing the needed diagnostic.

[LOCALLY BUILT] The UI-only build completes with the configured Linux orb tools, Python 3.13.7 and Node.js 22.23.2.
The final diagnostic bundle SHA-256 is `d8ee25882adaa016b26da7e7627ae24ebf478f89582db53ca8d2e64329b6fd74`.
It supersedes preparatory bundle `bc162afa36da9b7325ecff92c33b13366f8087379c73012e554a290fc00f38ed`, which missed folders without any poster elements.
The preparatory bundle reached the Mac but did not reach the console.
No native source, firmware handling, account setting or catalogue source changes in this diagnostic batch.
[PENDING CONSOLE TEST] Installing this candidate requires explicit approval and the current console address before any automated console connection.
Only `webui/app.bundle.js` would change while Nuvio is closed. Keep `/data/nuvio/` untouched.
No new commit, push, PR update or console installation occurred during preparation.

[CONSOLE FILE VERIFIED] The owner approved the exact-file replacement and supplied the current PS5Upload service address.
The connected Mac runner used the source-inspected PS5Upload Minion 9.4.1 file API on 2026-10-31.
The original console bundle contained 3170318 bytes. Its SHA-256 was `90a95a0db084d96a7ca864aac28a2590af0b053c22bebfaf208e8e3475e5fc53`, matching the expected label-fix candidate.
The replacement contained 3171336 bytes. The binary upload returned HTTP 200.
A complete four-chunk readback, capped at 1 MiB per chunk, matched SHA-256 `d8ee25882adaa016b26da7e7627ae24ebf478f89582db53ca8d2e64329b6fd74`.
The transfer changed only `/data/homebrew/PPSA99997/webui/app.bundle.js`. It did not touch `/data/nuvio/` or launch an app or payload.
No transfer error, cancellation or recovery occurred. No credentials, account state or private service address entered the repository.
The file check confirms installation, not console execution or a fix for missing posters, empty folders or storage omission.
[PENDING CONSOLE TEST] Reopen Nuvio and sample one affected folder with the installed diagnostic.
Live collection size, source state and the cause of the missing configuration remain unverified.
No new commit, push or PR update occurred.

### HBO Max collection observations and artwork request candidate, 2026-10-31

[OWNER-REPORTED] The diagnostic candidate opened the profile selector. The owner selected a profile, opened HBO Max and reported a blank screen.
[READ-ONLY CONSOLE LOG] The Mac runner retrieved the last 1048576 bytes of `/data/nuvio/evo.log`, starting at offset 4185981.
The file contained 5234557 bytes at stat. Extraction included only complete lines after the latest BUILD boundary in that tail.
Only fixed diagnostic fields left the Mac. Sample timestamps and build identity were not extracted, so exact test-session correlation remains unverified.
Four folder samples report 49 Trakt tabs, zero addon or TMDB tabs, zero loading tabs and zero source errors.
They report 1016 items, 1015 without artwork fields, zero items marked as loading and 1016 poster placeholders.
The focused poster reports a visible box and positive opacity, but no image provider. The WebP probe reports successful decoding.
Two Home samples report four loaded images, 242 pending images and 116 deferred images.

All six samples report live `collectionsState` length 757956 characters, above the 524288-character snapshot limit.
This confirms that the measured live value meets the inspected exporter's omission condition.
It does not prove the earlier downloaded file came from that exact live value, or establish a cause for session loss.
The snapshot exporter and persistence policy remain unchanged in this candidate.

[SOURCE-VERIFIED] The collection Trakt loader reads entity image fields but sends no extended-information parameter.
The existing library-list loader requests `extended=full,images`.
The [Trakt image guide](https://docs.trakt.tv/docs/images) requires extended information for image fields when available.
It also requires image caching. This change does not add caching or establish successful CDN access from PS5.
The guarded pinned replacement now requests `full,images` for collection lists, matching the existing library loader.
This repairs a request omission consistent with the missing fields. Actual provider responses and console recovery remain unverified.

[HOST-VERIFIED] A temporary fixture exercised the actual collection request, mapper, normalizer and Trakt URL normalizer.
The fixture reproduced missing movie and series artwork before the change, then returned expected HTTPS poster URLs after it.
Asymmetric IDs, descending title sorting, page three of four and source-error propagation retained their expected results.
The response fixture follows the documented minimal-versus-extended contract. It is not a live Trakt or PS5 test.
[RENDER-INSPECTED] Chromium 156 rendered the actual poster markup with isolated dependency stubs and synthetic artwork at 1100x680, scale two.
DOM checks found one placeholder before, one decoded 300-pixel image after and two focusable cards.
The comparison labels identify the host fixture and distinguish it from a PS5 capture. This does not validate full folder layout or controller behavior.
[FAILED HOST FIXTURE ATTEMPT] The first renderer run omitted the existing lazy-image helper and failed before browser capture.
Loading that helper corrected the fixture. No runtime source change was needed for that failure.

[LOCALLY BUILT] `NUVIO_WORK_DIR="$PWD/build/controller" make ui` completed with Python 3.13.7 and Node.js 22.23.2 on Linux x86-64.
The artwork candidate contains 3171381 bytes. Its SHA-256 is `612a9456fdaeaf50ddc0e4fb2b542bd6b604891541e6bbf778969e11f20c0f5f`.
No native source changed. No native rebuild, firmware change, account write, new commit or push occurred.
[PENDING CONSOLE TEST] The artwork candidate is not installed. Close Nuvio and obtain approval before replacing only `webui/app.bundle.js`.
Preserve `/data/nuvio/`. Keep the installed diagnostic bundle until the next controlled replacement.
New Movies and New Series need separate evidence. Their source types and failure states remain unknown.

[CONSOLE FILE VERIFIED] The owner closed Nuvio and confirmed the requested artwork candidate replacement on 2026-10-31.
The Mac runner verified the downloaded candidate's 3171381-byte size and SHA-256 before console writes.
The complete preflight read matched diagnostic bundle `d8ee25882adaa016b26da7e7627ae24ebf478f89582db53ca8d2e64329b6fd74`, containing 3171336 bytes.
The PS5Upload binary upload returned HTTP 200 after sending 3171381 bytes.
The final stat and complete four-chunk readback matched SHA-256 `612a9456fdaeaf50ddc0e4fb2b542bd6b604891541e6bbf778969e11f20c0f5f`.
The runner also compared the complete readback bytes with the local candidate and found an exact match.
Only `/data/homebrew/PPSA99997/webui/app.bundle.js` changed. No retry, recovery, account access, app launch or other console write occurred.
No new commit or push occurred. The transfer preserved `/data/nuvio/`.
[PENDING CONSOLE TEST] Reopen Nuvio and check HBO Max artwork. File verification does not establish successful artwork delivery or rendering.

[OWNER-CONFIRMED ON 12.70] After reopening Nuvio, the owner confirmed that HBO Max posters appear without opening a title and returning.
This follows installation and complete readback verification of artwork candidate `612a9456fdaeaf50ddc0e4fb2b542bd6b604891541e6bbf778969e11f20c0f5f`.
The report confirms recovery for the tested HBO Max folder. No recording or fresh diagnostic log accompanied this confirmation.
New Movies, New Series, long-term session persistence and pointer presentation remain separate open checks.
No additional console write, commit or push occurred during this confirmation.

### Remaining artwork-only folders and public configuration inspection, 2026-10-31

[OWNER CLARIFICATION] The owner's earlier "both" reply did not confirm recovery for New Movies or New Series.
The owner reports artwork-only destinations across the New Movies row, Networks, Actors, By Decade and Anime.
Keep the confirmed HBO Max artwork result separate from these unresolved folders.

[READ-ONLY CONSOLE LOG] A later tail read retrieved 1048576 bytes from offset 4536153 of a 5584729-byte log.
Sanitized extraction used complete lines after the latest BUILD boundary. Sample timestamps and exact navigation correlation remain unverified.
The six available groups contain Home and one Netflix folder sample, not the newly reported failing folders.
Netflix reports 49 Trakt tabs, 1155 items, zero items without artwork and zero loading or source-error tabs.
Its image sample reports 29 loaded images, 1126 pending images and zero placeholders or failures.
No zero-item or source-error folder sample appears in this bounded extraction.
The six-sample page budget prevents this retrieval from establishing the state of folders visited later.
Do not treat Home or Netflix observations as evidence that the other folders work.

[READ-ONLY PUBLIC CONFIGURATION] The installed `webui/nuvio.env.js` contains 1420 bytes.
Its SHA-256 is `cd060e4a6416592cd738f52dd47327191639d2e1316aa3447e4ce0dc26ab5bc7`.
Nonexecuting inspection found one strict-JSON configuration object. Both `TMDB_API_KEY` and `TRAKT_CLIENT_ID` exist as nonempty strings.
The initializer copies its own entries into the runtime object, overwriting matching keys, then assigns that object to `__NUVIO_ENV__`.
This is static wiring evidence, not observed execution, credential validity, service access or immunity to later script changes.
The host-built runtime also contains both nonempty fields. No configuration value left the inspecting process.
[FAILED INSPECTION ATTEMPT] The initial narrow initializer matcher failed to parse the installed script.
Strict JSON extraction and local control-flow inspection resolved that limitation without executing the file.
The matcher failure did not establish an invalid configuration or missing keys.

[SOURCE-VERIFIED] Modern collection rendering skips source rows without items or loading placeholders, including empty and failed source results.
This shared presentation can leave only the seeded folder artwork. It does not identify why these particular sources fail to provide visible rows.
[PENDING CONSOLE TEST] Start a fresh Nuvio session and open New Movies before visiting working streaming folders.
Collect its bounded source diagnostics before choosing another source-loading fix.
No runtime, public configuration, account data or console file changed during these inspections. No commit or push occurred.

### Fresh New Movies sample and response diagnostic candidate, 2026-10-31

[OWNER TEST] The owner closed Nuvio, reopened it and went directly to New Movies before reporting readiness after the requested wait.
[READ-ONLY CONSOLE LOG] The bounded tail contained 1048576 bytes from offset 4792719 of a 5841295-byte log.
The file size remained stable during retrieval. No short read, rotation or truncation occurred.
Extraction included complete lines after the latest BUILD boundary. Independent timestamp correlation remains unverified.
Three explicit `newmovies` samples report 18 TMDB tabs, zero other providers, zero loading tabs and zero source errors.
All three contain zero items and zero poster elements. This is an empty-data state, not pending poster images.
The other three groups contain Home samples. Live collection length remains 757956 characters.

[CONFIGURATION COMPARISON] The host-built `nuvio.env.js` also contains 1420 bytes and matches the inspected console file's complete SHA-256.
This verifies packaged-file equality, not live service access or successful browser execution.

[SOURCE-VERIFIED] The folder JSON helper converts a rejected JSON parse into null before checking the HTTP status.
The TMDB movie-collection helper returns an empty array for an unsuccessful HTTP response.
Either policy can conceal a failure behind an empty result. Neither is established as the cause of the New Movies samples.

[PRIVATE DIAGNOSTIC CHANGE] The existing PS5 diagnostic now records HTTP status, JSON parse state, coarse payload shape and fixed array lengths.
The observed fields are results, items, cast, crew and parts. An absent array reports -1, distinct from a valid empty array.
JSON state is 1 for parsed data, 0 for a parse rejection and -1 when collection HTTP failure skips parsing.
The callback logs at most 24 responses per page, only on a visible collection-folder route with the native hook present.
It does not read a second response body, change request parameters, alter return values or replace existing error handling.
Existing folder samples also count fixed TMDB source kinds. Unknown kinds become other.
No keys, addresses, source identifiers, titles, response contents or raw errors enter the new messages.

[HOST-VERIFIED] A temporary harness exercised the actual JSON helper, collection method and PS5 diagnostic before and after source adaptation.
The baseline reproduced null after a rejected successful-response JSON parse and an empty array after collection HTTP failure.
The adapted code distinguishes malformed JSON, valid null, empty results, unexpected array roots and API error objects.
The checks preserve response and payload identity, collection item IDs and poster URLs, HTTP errors and original rejection objects.
An asymmetric source fixture reports two lists, one person, one network and one unknown kind.
Hidden and non-folder routes produce no response reports. The no-hook control has no callback or added diagnostic requests.
A failed diagnostic transport does not change successful results. Reporting stops at 24 responses, with each message below 200 characters.
Credential, address, title and error sentinels remain absent from output. These controls do not establish the console's actual HTTP or JSON outcome.

[LOCALLY BUILT] The UI-only build completed with Python 3.13.7 and Node.js 22.23.2 on Linux x86-64.
The response diagnostic bundle contains 3172635 bytes. Its SHA-256 is `ee5118009509aeb00d4ba32de93cf9add6efd4979be0cee7560ca7e1001bf08b`.
No native source, layout, account state, catalogue settings or public runtime configuration changed in this batch.
[PENDING CONSOLE TEST] Obtain approval before replacing only `webui/app.bundle.js` while Nuvio is closed.
Keep the confirmed artwork fix and `/data/nuvio/` intact. Capture New Movies before choosing a data-loading fix.
The response diagnostic is not installed. No new commit or push occurred.

[CONSOLE FILE VERIFIED] The owner closed Nuvio and approved the response diagnostic replacement on 2026-10-31.
The Mac runner reverified the local candidate's 3172635-byte size and expected SHA-256 before console writes.
Complete preflight readback matched artwork bundle `612a9456fdaeaf50ddc0e4fb2b542bd6b604891541e6bbf778969e11f20c0f5f`, containing 3171381 bytes.
The binary upload sent 3172635 bytes and returned HTTP 200.
Final stat and complete four-chunk readback matched SHA-256 `ee5118009509aeb00d4ba32de93cf9add6efd4979be0cee7560ca7e1001bf08b`.
The runner also verified complete byte-for-byte equality with the local candidate.
Only `/data/homebrew/PPSA99997/webui/app.bundle.js` changed. No error, retry, recovery, app launch or other console write occurred.
The transfer preserved `/data/nuvio/`. No new commit or push occurred.
[PENDING CONSOLE TEST] Reopen Nuvio and go directly to New Movies to capture source kinds and response diagnostics.
Installed-file verification does not establish the failing request's status, JSON validity or cause.

### Empty New Movies responses and saved rating filters, 2026-10-31

[READ-ONLY CONSOLE LOG] After the owner reported readiness, the Mac runner read a bounded tail from the existing log.
The file contained 6119358 bytes. The read retrieved 1048576 bytes from offset 5070782.
Another 61 bytes appeared afterward. No rotation or short read occurred.
Extraction used complete lines after the latest BUILD boundary. Independent timestamp and artifact correlation remain unverified.
Five response reports show HTTP 200, parsed object payloads and zero results, without an API error object.
Three New Movies groups show 18 TMDB DISCOVER sources, zero items, zero loading sources and zero source errors.
No poster elements exist in those samples. These are empty data, not pending image downloads.
Five captured responses do not establish the outcome of all 18 requests.

[READ-ONLY ACCOUNT INSPECTION] The owner previously requested direct inspection of the catalogue configuration.
The Mac runner used the existing session and selected profile for a GET request to `sync_pull_collections`.
PostgREST documents GET function requests as read-only database transactions.
No login, session refresh, cloud POST, cloud write or console file write occurred.
Credentials and the cloud response stayed in process memory. Only fixed aggregate fields left the process.

[FAILED INSPECTION ATTEMPT] The first Python request failed before an HTTP response.
Its handler discarded the exception, so the precise failure remains unknown.
Local inspection found no Python CA certificates. This supports a trust-store hypothesis, not a confirmed diagnosis.
A single system-curl request then succeeded with HTTP 200 and default verified TLS.
Certificate verification remained enabled. No account token refresh was necessary.

The unnormalized cloud payload contains 11 collections, 362 folders and 1755 sources.
Source counts are 822 TMDB and 933 Trakt, with no addon or other providers.
TMDB source kinds are 394 DISCOVER, 326 COLLECTION and 102 COMPANY.
The public New Movies folder contains 18 DISCOVER sources.
All 18 omit `voteAverageGte` and `voteAverageLte`, rather than storing null or zero.
All 18 set `voteCountGte` to numeric 20.
Their other filter key names are `withGenres`, `withOriginalLanguage` and `year`.
No private titles, identifiers, addresses, tokens or complete source definitions enter this record.

[HOST-REPRODUCED] The pinned collection normalizer passes nullable rating filters through `Number`.
An omitted bound first becomes null. Normalizing that value again changes null to zero.
The actual cloud-pull, profile-store, collection-read and discover-request code reproduces this path with a synthetic source matching the observed numeric fields.
Its RPC boundary supplies synthetic data. Its request boundary records the constructed query without contacting TMDB.
Before the fix, the omitted ceiling becomes `vote_average.lte=0`. The minimum vote count remains 20.
After the fix, the ceiling stays absent from the query. The minimum vote count still remains 20.
This links an actual saved-input condition to a reproducible frontend defect, not observed recovery on the PS5.

[LOCAL FIX] The source adapter now checks for null or undefined before converting the three nullable rating and vote-count filters.
Explicit numeric zero and configured limits remain valid. The fix does not reinterpret existing zeros or change cloud configuration.
No artwork, layout, controller mapping, public runtime configuration, native source or firmware behavior changed in this batch.

[HOST-VERIFIED] The regression uses the pinned public collection-source interface and four JSON normalization cycles.
It covers missing and null filters, explicit null bounds, explicit zeros, asymmetric numeric limits and integer vote counts.
The unmodified fixture fails with an assertion. The adapted fixture passes.
A separate actual-source harness checks public import/export and movie and TV request construction, including explicit ceilings of zero and 8.25.
Genre and release-date filters remain unchanged. The fixture matches the pinned source functions exactly.
[FAILED HARNESS EXPECTATION] An initial scratch check also expected an unchanged second cloud pull to become a no-op.
That assertion failed after the rating fix because the separate optional `tmdbId` field changes from null to zero.
The final bounded check isolates the rating-query contract. The optional-ID issue remains unchanged and has a separate suggested follow-up.

[LOCALLY BUILT] The UI build and `make check` pass on Linux x86-64 with Python 3.13.7 and Node.js 22.23.2.
The check runs 65 tests, documentation checks, source-pin checks and private-artifact checks.
The UI-only candidate contains 3172705 bytes. Its SHA-256 is `92b8e28b347ad12cbb99efc0a715467a4a363832eb4ed079fcebf3790c413717`.
The generated frontend patch records the three null guards. No generated binary enters source control.
[MAC FILE VERIFIED] The runner downloaded the candidate into Downloads and verified its complete size and SHA-256.
The destination did not exist, so no existing file changed. This preparation made no console request or write.
[PENDING CONSOLE TEST] This candidate is not installed. Obtain approval while Nuvio is closed before replacing only `webui/app.bundle.js`.
Preserve `/data/nuvio/` and test New Movies first. Other reported empty categories still need their own console checks.
The last verified installed bundle remains `ee5118009509aeb00d4ba32de93cf9add6efd4979be0cee7560ca7e1001bf08b`.
No new commit, push, merge or deployment occurred.

[CONSOLE FILE VERIFIED] The owner closed Nuvio and approved the catalogue-filter UI replacement on 2026-10-31.
The Mac runner verified the local candidate's 3172705-byte size and expected SHA-256 before writing.
Complete preflight readback matched the 3172635-byte response diagnostic bundle, SHA-256 `ee5118009509aeb00d4ba32de93cf9add6efd4979be0cee7560ca7e1001bf08b`.
One whole-file binary upload sent 3172705 bytes and returned HTTP 200.
Final stat and complete four-chunk readback matched SHA-256 `92b8e28b347ad12cbb99efc0a715467a4a363832eb4ed079fcebf3790c413717`.
The complete installed bytes also matched the local candidate byte-for-byte.
All service requests returned HTTP 200. No failed attempt, retry or recovery occurred.
Only `/data/homebrew/PPSA99997/webui/app.bundle.js` changed. No app launch or other console file write occurred.
The transfer preserved `/data/nuvio/`, account state, settings, native playback files and firmware work.
No cloud request, commit, push or merge occurred during installation.
[PENDING CONSOLE TEST] Reopen Nuvio, select the usual profile and open New Movies first.
Installed-file verification does not establish catalogue recovery, image loading or controller behavior on the PS5.

[OWNER-CONFIRMED ON 12.70] After the requested New Movies test, the owner reports "it works!".
This confirms recovery of the tested New Movies destination after installing the catalogue-filter candidate.
The verified installed bundle SHA-256 is `92b8e28b347ad12cbb99efc0a715467a4a363832eb4ed079fcebf3790c413717`.
No fresh screenshot, recording or diagnostic log accompanies this confirmation.
Other affected categories, playback transitions and long-term session persistence still need separate checks.
No additional console write, commit or push occurred during this confirmation.

[OWNER-CONFIRMED ON 12.70] The owner also confirms that New Series loads after the requested follow-up test.
This uses the same verified catalogue-filter candidate. No new artifact or console write occurred.
Networks, Actors, By Decade and Anime remain pending, alongside playback transitions and long-term session persistence.

[OWNER-CONFIRMED ON 12.70] The owner confirms Networks, By Decade and Anime work with the catalogue-filter candidate.
Play options now works. Closing and reopening Nuvio preserves access to the actual profiles without another sign-in in this test.
This is one close/reopen result, not a long-term session-expiry test.
[OWNER-REPORTED FAILURE] Actors still does not work. The precise selected actor and failure presentation remain unrecorded.
After playback, Back returns from the stream list to title details, but further Back cannot leave that page.
This confirms the earlier suspected navigation failure was not merely difficulty locating the sidebar.
These reports apply to UI bundle `92b8e28b347ad12cbb99efc0a715467a4a363832eb4ed079fcebf3790c413717`.
No new screenshot, log capture, console write, commit or push accompanies these reports.

### Restored title Back fallback and Actors investigation, 2026-10-31

[SOURCE-VERIFIED] Browser recreation restores a route without its previous navigation stack.
Stream Back reconstructs title details with history replacement and no stack push.
At that root, ordinary Detail Back delegates to browser history, which has no predecessor in the reproduced case.
[LOCAL FIX] On PS5, title details now reuse the existing Home return when the router stack is empty.
Explicit Search return still takes priority. Open menus close before page navigation.
Stacked navigation and non-PS5 behavior remain unchanged.

[HOST-VERIFIED] A regression exercises the public detail Back handler with open menus, explicit Search return and stacked navigation.
It also covers non-PS5 behavior and the existing explicit Home return.
An actual-source Chromium fixture reproduces the root-history trap before the fix.
After the fix, Back dismisses Play options, then reaches Home with a visibly focused catalogue card.
The fixture starts with browser history length one and an empty router stack.
The inspected recording shows that sequence. Synthetic Home metadata appears duplicated in the fixture.
The fixture anomaly is not established as production behavior. No layout change accompanies this fix.
Host rendering and keyboard input do not establish PS5 controller behavior.

[LOCALLY BUILT] The UI-only build uses Linux x86-64, Python 3.13.7 and Node.js 22.23.2.
The candidate contains 3172751 bytes, SHA-256 `8aefb0a685f9cfe4c0da812e6a932d790a0dbac21f990b66e29480575e48631a`.
`make check` passes 66 tests, documentation checks, source-pin checks and private-artifact checks.
The writing checker reports zero hard violations. `git diff --check` also passes.
No native source changed in this batch. The generated frontend patch includes the Back guard.
[PENDING CONSOLE TEST] The Back candidate is not installed. Obtain approval while Nuvio is closed before replacing the UI bundle.
The verified installed bundle remains `92b8e28b347ad12cbb99efc0a715467a4a363832eb4ed079fcebf3790c413717`.

[READ-ONLY ACCOUNT INSPECTION] Actors contains 58 folders and 216 sources, all using Trakt.
There are 174 movie sources and 42 TV sources. All list identifiers are positive JSON integers.
The first sampled folder has three sources. Their exact frontend movie requests return HTTP 200 with empty arrays.
Their pagination reports zero items and zero pages. This sample does not identify the owner's selected actor.
For the first source, two bounded controls also return HTTP 200 and empty arrays.
One requests all documented item types without sorting. The other requests movies without sorting.
Both report page one, limit 50, zero items and zero pages.
The saved sort choices differ from the frontend defaults. Removing them does not recover this sampled list.
These results do not establish why the list is empty or whether other Actors lists fail.
No speculative Trakt or TMDB change is justified by this sample.
The selected actor and its precise failure presentation remain pending owner clarification.
Verified TLS stayed enabled. No account Authorization was sent to Trakt, and no cloud or console write occurred.
No new commit, push or merge occurred.

[OWNER-REPORTED ON 12.70] The selected actor is Adam Sandler. Its folder shows only background artwork.
The owner reports the same presentation with other actors, without naming them.
[READ-ONLY ACCOUNT INSPECTION] A bounded cloud GET confirms one Adam Sandler folder, matching the previously sampled first Actors folder.
Its three sources are Trakt movie lists. The earlier empty responses therefore apply to the owner's named failing destination.
No additional Trakt request repeated the controls. Why those lists return no titles remains unknown.
Other actors' responses and the PS5 request outcomes remain unverified.

[CONSOLE FILE VERIFIED] The owner closed Nuvio and approved the pending Back candidate replacement on 2026-10-31.
The Mac runner verified the 3172751-byte local candidate before writing.
Complete preflight readback matched the expected 3172705-byte installed bundle, SHA-256 `92b8e28b347ad12cbb99efc0a715467a4a363832eb4ed079fcebf3790c413717`.
One whole-file binary upload sent 3172751 bytes and returned HTTP 200.
Final stat and complete four-chunk readback matched SHA-256 `8aefb0a685f9cfe4c0da812e6a932d790a0dbac21f990b66e29480575e48631a`.
The complete installed bytes also matched the local candidate byte-for-byte.
All installation requests returned HTTP 200. No failed installation attempt, retry or recovery occurred.
Only `/data/homebrew/PPSA99997/webui/app.bundle.js` changed. No app launch or other console write occurred.
The transfer preserved `/data/nuvio/`, account state, settings, native playback files and firmware work.
[PENDING CONSOLE TEST] Reopen Nuvio, play a title, stop playback and press Back through the stream list and title details.
Expect Home after title details. If Play options is open, Back must dismiss it before leaving the page.
Installed-file verification does not establish controller recovery. Actors remains unresolved.
No new commit, push or merge occurred.

[OWNER-CONFIRMED ON 12.70] The owner confirms the playback-return Back fix works with the installed Back candidate.
The owner also confirms Adam Sandler fails on another Nuvio device and requests no further Actors changes.
That comparison does not identify the upstream empty-list cause. Actors investigation stops without changing the saved sources.

### Triangle Search and text-entry candidate, 2026-10-31

[OWNER-REPORTED ON 12.70] Opening Search from navigation does not open the keyboard.
X on the focused Search text box also does not open the keyboard in the installed Back candidate.
The owner requests Triangle to open Search and the keyboard automatically.

[READ-ONLY CONSOLE LOG] After an isolated Triangle press, the Mac runner reads a bounded newest log tail.
The initial log size is 7330782 bytes. The read contains 1048576 bytes from offset 6282206.
The file grows by 61 bytes during inspection, without a short read or detected rotation.
The newest key record is F1 with numeric keyCode 112.
The preceding public keys are Enter, Enter, ArrowRight, Enter, Enter, ArrowDown and Escape.
The analyzed segment has 108 keydown records and no native Triangle or Options press-log records.
These are segment counts, not endpoint counters. The counter endpoint was not requested.
Extraction uses complete lines after the latest available build boundary.
No independent timestamp, event identifier or installed-bundle correlation accompanies that boundary.
The owner's isolated action and newest key support the F1 mapping, without proving a native controller edge.
No console file write, app launch or account request occurs during this read.

[REJECTED HOST EXPERIMENT] The adapter initially handles observed F1/112 and the existing native Triangle event as a Search shortcut.
It blocks profile selection, authentication, onboarding, playback and open dialogs.
Repeated presses during navigation do not remount Search. An existing query remains available when already on Search.
The shortcut uses the standard browser prompt to request text, then Nuvio's existing query handler.
X redirected to the focused Search field uses the same text request.
Cancel preserves the current query and does not submit another search.
This does not establish a PS5 keyboard API or prompt support. No invented native IME declaration enters the candidate.

[HOST-VERIFIED] `make check` passes 67 tests, including accepted text, cancellation, repeat suppression and blocked routes.
The input regression also covers navigation races, X on Search and existing Options/Square behavior.
An actual-source Chromium fixture accepts F1, opens a native browser prompt and submits the entered query Arrival.
DOM checks confirm the Search route, query Arrival, input value Arrival and visible input focus.
A second prompt carries Arrival as its default. Dismissing it preserves the query and input.
The inspected screenshot shows the focused Search field and the expected synthetic empty results.
The first fixture load failed because translation resources were relative to the scratch directory.
Adding the correct UI base path fixed the fixture without a production change.
Browser automation timed out waiting for key dispatch while the prompt blocked the renderer.
The explicit dialog status and accept commands resolved it and allowed the DOM checks.
These host results do not establish PS5 prompt or keyboard behavior.

[LOCALLY BUILT] The UI-only candidate contains 3173948 bytes.
Its SHA-256 is `0a9792358a1565aafcc9a53b52e9f887a8046c7b0aff6cdb6f026feba370d31f`.
The host remains Linux x86-64, Python 3.13.7 and Node.js 22.23.2.
No native source, playback handoff, firmware behavior or account configuration changed in this batch.
[OWNER DIRECTION] The owner rejects the separate prompt and requires the existing Search text box with the system keyboard.
The prompt experiment was never installed. Its hash above is superseded, not a console test candidate.
The adapter removes the prompt without testing it on PS5.
No commit, push or merge occurred.

[LOCAL CANDIDATE, EXISTING SEARCH UI] The revised shortcut removes the separate prompt and retains Nuvio's existing Search text box.
PS5 Search now renders before awaiting cached profile decoration. Its existing background request still refreshes profile decoration.
The adapter focuses the real text box before awaiting route completion, inside the F1 event handler.
This removes an asynchronous boundary before the keyboard request. Whether that boundary caused the console failure remains unverified.
The native Triangle bridge still focuses Search, but a polled event does not establish a browser user gesture.
The observed browser F1 event provides the direct input path.
Scheduled Search refreshes reuse the existing result-only renderer while the text box is active.
They do not replace the input or clear its query. Other platforms retain the original rendering and cached-profile path.

[HOST-VERIFIED] The revised regression requires focus before the navigation promise resolves.
It checks F1, the native fallback, repeated presses, existing query preservation, blocked profiles, authentication, playback and dialogs.
The actual-source Chromium fixture receives a trusted F1 and focuses `searchInput` before that same key handler returns.
Typing Arrival updates the existing input and Nuvio query. Repeated F1 preserves both.
A forced background render preserves input-node identity, active DOM focus and the value Arrival.
The inspected final recording and screenshot show the existing Search UI without a prompt or replacement keyboard.
The synthetic search source returns no results intentionally. It does not test remote catalogue requests.
An initial scratch timing probe reset its flag between native event listeners and reported false.
Wrapping the actual key callback corrected the measurement and established synchronous focus.
No production timing workaround derives from that probe.
These checks do not establish automatic PS5 keyboard presentation.

[LOCALLY BUILT] The revised UI bundle contains 3173761 bytes, SHA-256 `86a2153b70a1f70be49921b87f5916480ca9d59aa2b67191e3fb58226437d549`.
`make check` passes 67 tests, documentation checks, source-pin checks and private-artifact checks.
The host remains Linux x86-64, Python 3.13.7 and Node.js 22.23.2.
No native playback or firmware change accompanies this UI-only candidate.
[PENDING CONSOLE TEST] The revised candidate is not installed. Obtain approval while Nuvio is closed before replacing only the UI bundle.
Verify Triangle opens the existing Search screen and the native keyboard while its text box has focus.
If only focus works, record automatic keyboard opening as failed. No prompt fallback is part of the candidate.
No new commit, push or merge occurred.

[CONSOLE FILE VERIFIED] The owner closed Nuvio and approved the revised no-prompt Triangle candidate on 2026-10-31.
The Mac runner verified the local candidate as a regular file containing 3173761 bytes.
Complete preflight readback matched the installed Back candidate, 3172751 bytes, SHA-256 `8aefb0a685f9cfe4c0da812e6a932d790a0dbac21f990b66e29480575e48631a`.
One whole-file binary upload sent 3173761 bytes and returned HTTP 200.
Final stat and complete four-chunk readback matched SHA-256 `86a2153b70a1f70be49921b87f5916480ca9d59aa2b67191e3fb58226437d549`.
The complete installed bytes also matched the local candidate byte-for-byte.
All installation requests returned HTTP 200. No failed attempt, retry or recovery occurred.
Only `/data/homebrew/PPSA99997/webui/app.bundle.js` changed. The rejected prompt candidate was not installed.
No app launch, cloud request or other console file write occurred.
The transfer preserved `/data/nuvio/`, account state, settings, native player files and firmware work.
[PENDING CONSOLE TEST] Reopen Nuvio, select the usual profile and press Triangle once on Home.
Report separately whether Search opens, the text box gains focus and the PS5 keyboard opens automatically.
Installation verification does not establish native keyboard behavior. No new commit, push or merge occurred.

### Search icons and native keyboard bridge, 2026-10-31

[OWNER-REPORTED ON 12.70] The installed `86a2153b70a1f70be49921b87f5916480ca9d59aa2b67191e3fb58226437d549` bundle opens Search on Triangle.
The text box has a focus outline, but the keyboard does not appear. Same-handler focus did not solve keyboard activation.
The owner supplies a TV photo with a blank Discover button and confirms that presentation predates this candidate.
The owner authorizes fixing Search presentation and keyboard entry. No further console installation occurs in this batch.

[READ-ONLY CONFIGURATION AND LOG] The Mac runner reads the selected profile from the existing downloaded snapshot, without refreshing account state.
Its public settings are modern Home, modern sidebar enabled, sidebar blur disabled, collapseSidebar false and Discover in Search.
searchDiscoverEnabled is true. These are snapshot values, not a new live settings export.
A bounded console log read covers a 65536-byte head and 262144-byte newest tail from a 7839892-byte file.
The head records IME module 0x96 loading and CommonDialog initialization, both returning zero, followed by native IME ready.
The newest complete build segment has no JS-error or unhandled-rejection records. No rotation or truncation appears during inspection.
Those startup results do not establish IME activation over a running browser. No console writes or keyboard activation occur.

[SOURCE-VERIFIED] SharpProspero commit `5dfdb4b0b166e83dc9ae275001afb695f12c7174` leaves browser ImeParam and WebViewParam untyped and NULL in its example.
It supplies no documented browser keyboard-enable bits or example of simultaneous WebBrowserDialog and native IME.
Its separate sceImeDialogInit parameter is not a declared browser ImeParam type. The port does not substitute either structure or guess flags.
Pinned EVO already supplies native IME initialization, UTF-16 buffers, result handling and completion polling.
Its browser branch does not poll the application keyboard. This matters for an explicit bridge, not the browser's automatic HTML-field keyboard.
The pinned frontend deliberately hides the collapsed modern-sidebar chip on Search. The candidate preserves that design and the existing Search geometry.
Discover, empty-state magnifiers and recent-history removal depend on a remote icon font in the pinned source.
The photo does not independently establish whether a font request failed. Local SVGs remove that dependency for these Search states.

[LOCAL IMPLEMENTATION] Triangle, sidebar entry and Search-field activation request the existing native PS5 IME through the console-local bridge.
The main-thread browser pump opens and polls it, independent of pad-read availability.
Accepted text updates the original input and its existing input handler. Cancellation preserves the query.
Concurrent opens return conflict rather than attaching a new page to an older keyboard result.
The native-only open preserves EVO's keyboard preference and refuses failure without its virtual-keyboard fallback.
A browser-related refusal does not latch native IME broken for the session. Existing non-browser keyboard behavior stays unchanged.
The browser remains open. Its undocumented pointers, parts and control values remain unchanged.
Native failure leaves a visible retry/Back message. Search text does not enter new bridge logs or persistent files.

[HOST-VERIFIED] `make check` passes 69 tests, documentation checks, source-pin checks and private-artifact checks.
The focused test_nuvio suite passes 31 tests. New checks cover Unicode acceptance, cancellation, duplicate requests, stale-route isolation and refusal.
The native endpoint harness checks queued, accepted, cancelled, busy, unavailable, retry and inactive-browser responses with a simulated keyboard backend.
Those checks do not call the PS5 IME or prove simultaneous dialogs.
The generated native and frontend bridge sources match the current adapters byte-for-byte.
An actual-source Chromium fixture uses the snapshot's public Search layout settings, without account data or addon requests.
DOM checks confirm one focused Search input, a Discover accessible name, local SVG icons and zero Search icon-font spans in tested states.
The no-results fixture retains the query Arrival. The unavailable-endpoint fixture displays the retry/Back message and keeps input focus.
The inspected 1920x1080, 2x captures cover initial Search, recent history, no results and unavailable native input.
The inspected host clip shows a real moving pointer over neighboring controls and F1 retaining Search input focus.
No host capture contains a PS5 keyboard. No host result establishes native-keyboard display or controller ownership on 12.70.
An initial recorder session restored a blank tab. Reopening with consistent restore settings fixed that test setup.
A subsequent 2x 1920-wide recording exceeded the encoder buffer. A 2x 1280-wide recording completed and passed visual inspection.
The archive command lacked zip. Python's standard zipfile implementation produced and verified the candidate archive instead.

[LOCALLY BUILT, NOT INSTALLED] `NUVIO_WORK_DIR="$PWD/build/controller" make build` compiles the complete PS5 title and reports integrity valid.
Build ID is `9ee9a542-nuvio_1031-1422`. Environment: Linux x86-64, Python 3.13.7 and Node.js 22.23.2.
The unstripped intermediate eboot.elf SHA-256 is `517e40d2834f1e8a1824e2f779ffdd644f3cf11829b34410c5a07a697c6e1dab`.
Candidate artifact identities:

| File | Bytes | SHA-256 |
|---|---:|---|
| eboot.bin | 35991012 | `e227cdbd8af5fe47d9a7b0a53c9d2fde2b6459e427452fc64f11fe3f023d9774` |
| app.bundle.js | 3176370 | `778857bc03332cccd7d06adfc3dba0cdaef25b43151d67125c095b4a20679b66` |
| Candidate ZIP, two files only | 16518897 | `060be5d79921f2a3ed0475585024820937614d58fd726acfd397504c1248b548` |

This is a two-file update candidate, not a complete title installation. It does not include the separate playback-resume thread's changes.
The source keeps the current firmware gate, native playback handoff and `/data/nuvio` persistence behavior intact.
[PENDING CONSOLE TEST] Obtain fresh approval with Nuvio closed before replacing the native title and UI bundle.
Opening native IME over WebBrowserDialog remains unverified. Initialization can refuse, and simultaneous controller or dialog behavior may differ on 12.70.
If the system refuses or behaves unsafely, stop that experiment. Do not substitute a virtual keyboard or close/reopen the browser silently.
First check Triangle from Home, native keyboard display, entered text in the same Search input and results.
Then check sidebar Search entry, cancellation, repeated entry and Circle return. Recheck playback and its browser return after the native update.
No new console install, account change, commit, push or merge occurs in this batch.

[CONSOLE FILE VERIFIED] The owner confirms Nuvio closed and approves the two-file Search keyboard update on 2026-10-31.
The Mac runner verifies the 16518897-byte candidate ZIP and its exact two entries against the hashes above.
Complete preflight readback verifies both installed files as regular files with stable metadata.
The previous native title contains 35989860 bytes, SHA-256 `df659ed39696606a60c3831e008d32d85c6f81a2414dba823c3fdfd0fed50ea1`.
The previous UI bundle contains 3173761 bytes, SHA-256 `86a2153b70a1f70be49921b87f5916480ca9d59aa2b67191e3fb58226437d549`.
The runner creates verified private local backups before either console write. Directory permissions are 0700 and backup-file permissions are 0600.
One whole-file binary upload replaces `/data/homebrew/PPSA99997/eboot.bin`, followed by complete readback and verification.
One whole-file binary upload then replaces `/data/homebrew/PPSA99997/webui/app.bundle.js`, followed by complete readback and verification.
Final native readback contains 35991012 bytes, SHA-256 `e227cdbd8af5fe47d9a7b0a53c9d2fde2b6459e427452fc64f11fe3f023d9774`.
Final UI readback contains 3176370 bytes, SHA-256 `778857bc03332cccd7d06adfc3dba0cdaef25b43151d67125c095b4a20679b66`.
Both complete readbacks match the candidate bytes exactly. Native readback uses 35 chunks and UI readback uses four, each at most 1 MiB.
All requests return HTTP 200: one token request, 18 stat requests, 78 reads, two upload-begin requests and two binary uploads.
No failed attempt, retry, timeout, transport failure, recovery or partial installation occurs.
Only the two approved console files change. No app launch, cloud/account request, settings change or other console write occurs.
The transfer leaves `/data/nuvio`, firmware and account state untouched. No commit, push or merge occurs.
[PENDING CONSOLE TEST] The two-file candidate is installed, but no console keyboard result exists yet.
Ask the owner to open Nuvio and select the usual profile first. Then test Triangle from Home in a separate step.
Installation verification does not establish keyboard display, native/browser coexistence, controller ownership, playback or playback return.

[OWNER-REPORTED ON 12.70, KEYBOARD DISPLAY FAILED] The owner confirms the Discover icon now appears, but the keyboard still does not appear.
This confirms the icon correction, not keyboard success or complete Search behavior.
The Mac runner reads one 262144-byte log tail at offset 8318985 from the 8581129-byte file.
The stat remains unchanged. No short read, rotation, truncation, expansion, activation request or console write occurs.
Complete lines after build marker `9ee9a542-nuvio_1031-1422` show IME module and CommonDialog initialization returning zero, then native IME ready.
They also show an actual panel-size call, then sceImeDialogInit with panel dimensions 872x556 and maximum text length 255.
sceImeDialogInit returns `0x00000000`, followed by `Search native keyboard open=1`.
The panel-size call's return code and subsequent IME statuses are not logged. The marker is not a new installed-file hash check.
The inspected build segment contains no JS-error or unhandled-rejection records.
This establishes an accepted native initialization request, not visible keyboard presentation or successful simultaneous dialogs.
Browser occlusion, IME lifecycle and controller ownership remain hypotheses. The available evidence does not identify the cause.
No further candidate or console replacement follows this result. Do not repeat a focus-only patch or guess browser flags.
[PENDING OWNER CHECK] Ask the owner to press Circle once on Search and report whether Search remains or returns to Home.
That observation can inform controller-routing diagnosis, but cannot independently prove which dialog owns input or draws the missing keyboard.

[OWNER-REPORTED ON 12.70] One Circle press returns from Search to Home after the invisible-keyboard attempt.
This confirms browser Back remains usable in that state. It does not establish IME status, input ownership or the cause of invisibility.

[SOURCE COMPARISON] The owner requests comparison with ProsperoStore's search intent.
Research inspects [ProsperoStore commit 22d5a44a053b4dad4f3a5867fe39d262a80a1b8c](https://github.com/blackbearreloaded/ProsperoStore/tree/22d5a44a053b4dad4f3a5867fe39d262a80a1b8c), without changing or running that application.
Its Triangle mapping queues search on Home. The main loop waits for Triangle release before opening the native sceImeDialog keyboard.
Accepted text updates the native storefront query. Cancel keeps the query. A refused open does not use its bundled custom keyboard.
Its [IME poll implementation](https://github.com/blackbearreloaded/ProsperoStore/blob/22d5a44a053b4dad4f3a5867fe39d262a80a1b8c/src/platform/ps5/ime.cpp#L102-L132) tolerates initial NONE for one second.
It checks GetResult and Term return codes, retaining ownership when termination fails. It suppresses storefront input while keyboard input is pending or active.
Current EVO instead terminates immediately on NONE and ignores those result and termination return codes.
These are source differences, not observations that NONE or termination failure occurred in the installed Nuvio candidate.
ProsperoStore renders its own native EGL surface. Its search path does not keep WebBrowserDialog open or demonstrate simultaneous system-dialog composition.
Its repository notes report scripted keyboard opening and closing, but retain typing and native-keyboard console qualification limits.
That evidence is not this owner's hardware validation or proof of a compatible Nuvio browser keyboard path.
The source-backed next diagnostic is an elapsed-time trace of IME status transitions, GetResult and Term return codes, and bridge/browser state transitions.
Do not transplant its one-second grace period as a confirmed fix without observing the installed candidate's post-init status.
No source behavior change, new candidate, console action, Remote Play stream, commit or push accompanies this comparison.

### Native keyboard lifecycle diagnostic, 2026-10-31

[HOST-VERIFIED, CONSOLE PENDING] The owner approves the next diagnostic build after the ProsperoStore comparison.
The adapter logs native IME status transitions and elapsed monotonic milliseconds after initialization.
Each open permits 16 transition records and checkpoints at one, five and ten seconds.
The trace records GetResult, Abort and Term return codes without changing their existing handling.
The bridge records state changes and whether the browser and keyboard remain open. It never records search text.
No grace period, keyboard replacement, browser flags or browser close/reopen change accompanies this diagnostic.

The orb has no running Docker daemon. The build uses this repository's configured cross-build pipeline, not an upstream bare make invocation.
Environment: Python 3.13.7, Node 22.23.2 and Debian Clang/LLVM 19.1.7, with the cached pinned SDK and target dependencies.
`NUVIO_WORK_DIR="$PWD/build/controller" make build` succeeds and reports `integrity: valid`.
Build ID: `9ee9a542-nuvio_1031-1459`.
Native title: 35991780 bytes, SHA-256 `3433ef7deddc36c67a89d2cea1afc33f7b031e7347e74f867a4b22732045ceae`.
Unstripped ELF SHA-256: `97a02b23c03344bae8f722cf880f251c036d34c4a9c9232aa27dbc9da1d23863`.
The browser bundle remains byte-identical to the installed candidate, SHA-256 `778857bc03332cccd7d06adfc3dba0cdaef25b43151d67125c095b4a20679b66`.
Only the native title needs replacement for this diagnostic.

`make check` passes all 69 tests with the repository tool environment. Documentation reports zero hard violations and 21 advisories.
An initial run without that environment fails an existing promotion harness under GCC's misleading-indentation warning.
The configured-tool rerun passes without changing that unrelated source.
A temporary ASan/UBSan probe executes the generated trace block through 200000 stable polls and exact checkpoint boundaries.
It confirms bounded stable polling and the 16-transition cap. The temporary harness initially fails its own indentation warning, then passes after correction.
Host compilation and trace tests do not establish visible IME presentation or browser/keyboard coexistence.
No console contact, installation, account change, commit or push occurs in this diagnostic build step.
[PENDING] Obtain closed-app confirmation and approval before replacing the native title. Then inspect one Triangle attempt and its bounded log trace.

[INSTALLED, KEYBOARD TEST PENDING] The owner confirms Nuvio is closed and approves the native diagnostic replacement.
The Mac runner verifies the archive and its sole native entry against the recorded hashes before console access.
The original installed native matches 35991012 bytes and SHA-256 `e227cdbd8af5fe47d9a7b0a53c9d2fde2b6459e427452fc64f11fe3f023d9774`.
The runner saves, fsyncs and rereads a private backup. Backup bytes match the original, with directory mode 0700 and file mode 0600.
One binary upload replaces only `/data/homebrew/PPSA99997/eboot.bin`.
Complete readback matches all 35991780 candidate bytes and SHA-256 `3433ef7deddc36c67a89d2cea1afc33f7b031e7347e74f867a4b22732045ceae`.
Preflight and final reads each use 35 chunks, at most 1 MiB each. Stat checks remain stable and every read is complete.
All requests return HTTP 200: one token, five stat, 70 read, one upload-begin and one upload-data request.
No failed attempt, retry, recovery or partial-install condition occurs.
No app launch, browser-file write, account-state write, other console write, commit or push occurs.
The installation approval is consumed. Any later replacement requires fresh approval and closed-app confirmation.
[PENDING OWNER CHECK] Open Nuvio and select the usual profile before the isolated Triangle test.

[OWNER-REPORTED ON 12.70, KEYBOARD STILL INVISIBLE] The owner opens the diagnostic and presses Triangle from Home.
After the requested ten-second wait, the owner reports only the Search page.
The Mac runner reads 262144 bytes from offset 8557102 in `/data/nuvio/evo.log`.
The initial file size is 8819246 bytes. The final size is 8819307 bytes, an increase of 61 bytes outside the read.
No rotation, truncation, short read or read failure occurs. Analysis includes complete lines after build `9ee9a542-nuvio_1031-1459` only.
IME module and CommonDialog initialization return zero. Native initialization returns `0x00000000` with panel dimensions 872x556.
The bridge advances from queued to open, with browser=1 and keyboard=1.
Native status remains RUNNING at 13, 1014, 5001 and 10006 milliseconds after initialization.
No GetResult, Abort or Term record occurs. The inspected segment contains no JS-error or unhandled-rejection record.
This rules out immediate NONE cleanup during this attempt. ProsperoStore's initial NONE grace period does not address this observed path.
The trace does not prove visible presentation, controller ownership or browser occlusion. The panel-size return code remains unmeasured.
The log inspection performs no console write, launch, activation or account request.
[PENDING DECISION] A native-keyboard comparison without an open browser could separate browser coexistence from a broader native IME problem.
That comparison is not implemented or authorized. Do not silently replace Search with a browser-closing keyboard flow.

### Browser-free native keyboard comparison candidate, 2026-10-31

[HOST-VERIFIED, NOT INSTALLED] The owner approves preparation of the proposed comparison. Installation still requires fresh approval and closed-app confirmation.
`NUVIO_IME_COMPARISON=1` enables a one-shot diagnostic in the native adapter. Normal builds omit this browser-closing path.
The frontend saves the Search query and selected profile through the existing one-use return snapshot, then flushes the console storage bridge.
The main-thread diagnostic requests browser closure and waits for FINISHED, NONE or INITIALIZED before opening the same native keyboard.
Negative or unknown browser status does not establish closure. Unconfirmed closure stops the experiment without opening IME.
The loopback server stays running. The diagnostic suppresses underlying native controls and ordinary browser state-machine transitions while it owns the session.
Accepted text updates the existing Search input after browser recreation. Cancellation preserves the saved query.
The returned page reads the result once without automatically reopening the keyboard on focus.
After 30 seconds, the diagnostic requests IME cancellation once. It waits for completion before native cleanup.
Browser reopening requires native status NONE. Unconfirmed abort or cleanup stops the experiment instead of stacking system dialogs.
Those failure paths can require closing Nuvio manually. This is a diagnostic candidate, not the intended final Search interaction.

`NUVIO_IME_COMPARISON=1 NUVIO_WORK_DIR="$PWD/build/controller" make build` succeeds with `integrity: valid`.
Build ID: `9ee9a542-nuvio_1031-1512`. Environment remains Python 3.13.7, Node 22.23.2, LLVM/Clang 19.1.7 and the pinned cached target dependencies.
Native title: 35993508 bytes, SHA-256 `6c5e9a59665f003d261dfb2ba498f858f99167c4ccfb854639f08efb2f32aaed`.
Unstripped ELF SHA-256: `34f24209a759197be12503cb827ea08f7d3ae84971eb2315a89d29f352b21b8e`.
Browser bundle: 3176693 bytes, SHA-256 `e9e442a725bb3e4357195fe987506ffbd3b4aaf118bfa5987c30e6184419e65f`.
The two-file diagnostic ZIP contains 16522028 bytes, SHA-256 `571859b8a461a7ada50df9e1100ed8cea99ac6ae3470ce8c6da5b3982e77a937`.
The ZIP contains only `PPSA99997/eboot.bin` and `PPSA99997/webui/app.bundle.js`, not a complete installation.

`make check` passes all 69 tests. Extended host cases cover selected-profile and Search-query return, accepted text and no automatic keyboard reopening.
A temporary ASan/UBSan native probe passes acceptance, cancellation, refusal, delayed closure, closure failure, abort timeout and cleanup-failure cases.
The probe also confirms a second request cannot repeat the experiment within the same native process.
These host simulations do not establish actual keyboard visibility, system-dialog composition, cleanup or Search restoration on 12.70.
No visual styling changes accompany this diagnostic. Native keyboard rendering requires the owner's console and remains unverified.
No console contact, file replacement, app launch, commit or push occurs during preparation.
[PENDING] Obtain approval for both file replacements after the owner closes Nuvio. Then perform one isolated Triangle comparison and inspect the lifecycle trace.

[INSTALLED, COMPARISON PENDING] The owner confirms Nuvio is closed and approves the two-file comparison installation.
The Mac runner verifies the archive, both entries and both installed originals before either replacement.
The original native matches 35991780 bytes and SHA-256 `3433ef7deddc36c67a89d2cea1afc33f7b031e7347e74f867a4b22732045ceae`.
The original browser bundle matches 3176370 bytes and SHA-256 `778857bc03332cccd7d06adfc3dba0cdaef25b43151d67125c095b4a20679b66`.
Both original backups are fsynced, reread and byte-verified before any replacement. The private directory uses mode 0700 and both files use mode 0600.
One binary upload replaces the native, followed by full readback verification. A second replaces the browser bundle, followed by full readback verification.
Final native readback matches all 35993508 bytes and SHA-256 `6c5e9a59665f003d261dfb2ba498f858f99167c4ccfb854639f08efb2f32aaed`.
Final browser readback matches all 3176693 bytes and SHA-256 `e9e442a725bb3e4357195fe987506ffbd3b4aaf118bfa5987c30e6184419e65f`.
Each native read uses 35 chunks. Each browser read uses four chunks. All chunks remain at most 1 MiB, with stable stat checks.
All 101 API requests return HTTP 200: one token, 18 stat, 78 read, two upload-begin and two upload-data requests.
No failure, retry, recovery or partial-install condition occurs. Only the two approved install files change.
No launch, activation, scan, account-state write, settings change, commit or push occurs.
The approval is consumed. No later replacement is authorized by this installation.
[PENDING OWNER CHECK] Open Nuvio and select the usual profile before the isolated Triangle comparison.

[OWNER-REPORTED ON 12.70, PARTIAL COMPARISON SUCCESS] The native keyboard visibly appears after Triangle with the browser closed.
The keyboard disappears before the owner can type. Search returns, but the owner reports Back and navigation do not work.
The owner then clarifies that Search results are visible. Do not classify this as a blank page or confirmed total JavaScript freeze.
The Mac runner reads one 262144-byte tail from offset 9135525 of the 9397669-byte log. Before and after sizes match.
The latest build marker matches `9ee9a542-nuvio_1031-1512`. No short read, rotation, truncation or read failure occurs.
Browser Close returns zero and browser status reaches FINISHED. Native initialization returns zero with panel dimensions 872x556.
IME status remains RUNNING at 25, 1007 and 5011 milliseconds, then reaches FINISHED at 6863 milliseconds.
GetResult returns zero with endStatus OK at 6864 milliseconds. Term returns zero at 6866 milliseconds.
The diagnostic confirms native cleanup, reopens the browser successfully, and records accepted bridge state 3 with keyboard=0.
No timed Abort occurs. The observed disappearance is not the diagnostic's 30-second timeout.
The trace does not explain the early OK or prove what text was accepted. Search text remains private.
Seventeen later Arrow/Enter keydowns reach the page's JavaScript logging hook. No Back/Escape key record appears in the captured segment.
The segment contains no logged JavaScript error or unhandled rejection. These facts do not establish correct focus or screen-handler processing.
The successful isolated display, compared with invisible RUNNING IME over the browser, supports a coexistence or presentation hypothesis.
It does not isolate whether presentation, controller ownership or another lifecycle difference accounts for that comparison.
The comparison fails full controller usability after return. Do not promote it as a working Search keyboard solution.
The log inspection performs no console write, activation, retry or relaunch. No new candidate follows this result.
[PENDING] Inspect the returned Search focus state before changing navigation or asking for another installation.

[OWNER-REPORTED, FOLLOW-UP] Search subsequently shows the adapter's "The PS5 keyboard could not open" message.
The owner confirms that exact message and expects a restart to permit another keyboard attempt. No restart result is recorded here.
A bounded follow-up reads 98731 bytes from offset 9397668, including one boundary-context byte and all 98730 newly appended bytes.
The log size remains 9496399 bytes before and after reading. No short read, rotation, truncation, retry or read failure occurs.
The new complete-line region contains accepted bridge state 3 followed by unavailable state 5, with browser=1 and keyboard=0.
No second native initialization, native-open, comparison-phase or IME-trace record appears.
Forty-five new keydown records include Escape before and after bridge state 5. No logged JavaScript error or unhandled rejection appears.
Browser lifecycle lines also show closure and another successful open, but the extracted evidence does not establish their trigger.
The diagnostic intentionally refuses a second comparison within the same native process. Its unavailable outcome uses the ordinary adapter error text.
The observed message therefore does not establish a second native IME initialization failure. The one-shot guard itself has no dedicated log record.
Restarting the process resets that guard in source. Repeating the diagnostic would not independently fix or qualify return navigation.
The read-only inspection makes no console write or activation. No later candidate, installation, commit or push occurs.

### Repeatable Search keyboard candidate, 2026-10-31

[HOST-VERIFIED, NOT INSTALLED] The owner approves temporary browser closure for normal typing and asks to batch the remaining work.
The native session now permits repeated requests after cleanup. It removes the one-shot guard and diagnostic typing timeout.
Search mount handles menu entry. Triangle and textbox activation remain explicit requests. Focus/rerender alone never opens IME.
Accepted text follows Search's own submit path with result autofocus. Cancel preserves the saved query and selected profile.
Browser closure and native cleanup still require confirmed status before the next dialog opens.
The adapter removes the diagnostic build flag and comparison-only path.

A host fixture using the actual pinned Router, FocusEngine and Search methods reproduces Back leaving restored Search for about:blank.
Restored Search has an empty stack, and Router.back requests browser history before its empty-stack Home fallback.
Search now dismisses item actions first, then replaces an empty-stack PS5 Search with Home instead of requesting unavailable browser history.
The regression covers overlays, nonempty stacks and non-PS5 behavior. It does not claim this explains every reported D-pad symptom.
After the fix, the host DOM shows accepted query Dune, focus on the first result, Right to the second result and Escape to Home.
An inspected host recording confirms those rendered states. Its Home destination and catalogue data are fixtures, not console account data.
An initial browser rerun used cached pre-fix modules. A fresh session loaded the fixed module and passed the same scenario.

`make check` passes 70 tests. The native endpoint regression also passes ASan/UBSan with sequential accept/cancel/retry sessions and five minutes of simulated typing time.
`NUVIO_WORK_DIR="$PWD/build/controller" make build` succeeds with `integrity: valid`, build `9ee9a542-nuvio_1031-1531`.
Environment remains Python 3.13.7, Node 22.23.2, LLVM/Clang 19.1.7 and the pinned cached target dependencies.
Native: 35992740 bytes, SHA-256 `f1f2ee1836f62cae5a0e27627ee887cc39c7d5b5134a8d8a4c064be3aadfea98`.
Unstripped ELF SHA-256: `6200430f1dd4275554ad048c38af58c7f6a54252499e9c26417fcf5098f8203b`.
Browser bundle: 3176798 bytes, SHA-256 `847c0579b9747601c3748d8bfae9b814c3fec97a43815fabf0deb6bec58eb665`.
Two-file ZIP: 16520523 bytes, SHA-256 `f349fa6625773df7bdeeb76ba86e255361ad11bddf1afb1e03be1efccdc21cf7`.
The ZIP contains only the native title and browser bundle, not a complete installation.
No console access, replacement, commit or push occurs during this implementation batch.
A final check without the configured tool environment fails one compatibility test because GCC rejects existing misleading indentation in `scripts/promote.c`.
After sourcing `.cache/orb-tools/env`, the final check passes all 70 tests and the source-pin/private-artifact checks.
[PENDING] Obtain closed-app approval for both replacements. Console checks must cover typed text, cancel, repeated entry, result navigation and Circle to Home.

[INSTALLATION-VERIFIED, 2026-10-31 15:40:54 UTC] The owner replies "closed" and approves the two-file replacement.
The Mac runner backs up both originals, fsyncs them and rereads them before either console upload.
Both originals match the preceding diagnostic candidate's recorded sizes and hashes.
The runner replaces only `/data/homebrew/PPSA99997/eboot.bin` and `/data/homebrew/PPSA99997/webui/app.bundle.js`.
Full readbacks in chunks no larger than 1 MiB match this candidate's sizes, bytes and SHA-256 hashes above.
All 101 requests return HTTP 200. No failure, retry or partial installation occurs.
The runner does not launch Nuvio, activate the keyboard or write account/settings state. No commit or push occurs.
This approval covers the completed replacement only. Repeatable keyboard behavior and returned controller navigation remain pending owner validation.

[OWNER-CONFIRMED ON 12.70] The owner reports the installed keyboard candidate looks good after the Triangle/open-and-type check.
The owner then confirms submitted search results, D-pad navigation and Circle returning Home.
The owner also confirms another Triangle keyboard request without restarting, Circle cancellation and continued navigation on the returned Search screen.
These owner checks qualify the tested Search flow on 12.70, not every text-entry field or other firmware version.
The candidate remains installed with local source changes uncommitted and unpushed.

## Combined controller, Search and PR candidates, 2026-10-31

[LOCALLY BUILT, NOT INSTALLED] The owner requests one replacement PR for fork PRs #2 and #3 after PS5 testing, before any push.
Local branch `fix/ps5-controller-search-combined` retains the controller, collection and Search changes from this session.
It incorporates the playback-return bootstrap and regression from [PR #2](https://github.com/speed-y/nuvio-ps5-homebrew/pull/2).
That source matches [the original playback fix](https://github.com/speed-y/nuvio-ps5-homebrew/commit/d43d7387075298a7bad3374563b87f18c51969c1).
It incorporates the two font-inheritance adaptations and CSS patch export from [PR #3](https://github.com/speed-y/nuvio-ps5-homebrew/pull/3).
The exporter matches [the original font fix](https://github.com/speed-y/nuvio-ps5-homebrew/commit/e11699da6ec7510fd1894a0d1b34628e0f76830a).
Both PRs retain their standalone host evidence and artifact identities. Those older hashes do not identify this combined candidate.
The independent playback-resume timestamp work remains separate and unintegrated.

`make check` passes all 70 tests with the configured tool environment.
The extended profile-return regression preserves IDs, resume position and unrelated parameters while preventing automatic replay after return.
A Chromium fixture renders the actual shared NuvioDialog with the newly packaged stylesheet under Inter, DM Sans and Open Sans.
All three fonts load. Computed button families match the selected family, with 28px size and weight 500.
Inspected captures show focused, unfocused and destructive actions without clipping or overlap.
These host checks do not establish PS5 typography or playback behavior for this build.

The full native build succeeds with `integrity: valid`, build `9ee9a542-nuvio_1031-1547`.
Environment remains Linux x86-64, Python 3.13.7, Node 22.23.2 and LLVM/Clang 19.1.7 with pinned SDK v0.43 and pacbrew v0.39.
Receipt-verified local packaging succeeds. The title identity and firmware handling remain unchanged.

| Combined artifact | Bytes | SHA-256 |
|---|---|---|
| `eboot.bin` | 35992740 | `acca812b2c093b89e70f4759915a66c7bc3090031e5b10badd1bf007675cc01c` |
| `webui/app.bundle.js` | 3176955 | `127c2ca41ff80b28ef5124e5862357c482a65778250e971df755d2cd1723d010` |
| `webui/css/bundle.css` | 545760 | `f39827c380f935d0d899eccf38f0f337e684f5feee372f6944dd0dee1cdddede` |
| Three-file test ZIP | 16600096 | `1469d95a23835106e397f2c8747fb5d9927936510b9a4938ff97c601a5fc96e8` |
| Full title ZIP | 25900659 | `9c0b3f76e2ad964777466a4dc984b1468b40c8671b25af8e5b5dffe4acaa4811` |

No console contact, replacement, commit, push, new PR or closure occurs during this combination batch.
[PENDING] Obtain closed-app approval before backing up and replacing the three test files.
Then validate repeated playback return, themed controls and the previously confirmed Search flow on PS5.
After the owner accepts testing and authorizes a push, create one fork PR and close #2 and #3 with references to it.

[INSTALLATION-VERIFIED, 2026-10-31 15:53:06 UTC] The owner replies "closed" and approves the three-file replacement.
The Mac runner fully backs up, fsyncs and rereads all three originals before any upload.
Native and JavaScript originals match the preceding installed Search candidate's recorded sizes and hashes.
The original stylesheet has 545711 bytes, SHA-256 `88280017833dfe1ac395c76151a4647c92a0f91c27f0d9dfbcf33ac7c1089363`.
Only `/data/homebrew/PPSA99997/eboot.bin`, `webui/app.bundle.js` and `webui/css/bundle.css` change.
Full readbacks, in chunks no larger than 1 MiB, match all three candidate sizes, bytes and SHA-256 hashes above.
All 117 console API requests return HTTP 200. No failure, retry or partial installation occurs.
No app launch, keyboard activation, account/settings write, scan, commit, push or PR change occurs.
This approval covers the completed replacement only. Combined-candidate runtime testing remains pending owner validation.

[OWNER-CONFIRMED ON 12.70] The owner confirms all three requested checks pass on this installed combined candidate.
Playback returns to Nuvio without automatic replay, including the requested repeated check.
Menu/dialog fonts look consistent. Triangle, keyboard entry, search results and Circle return still work.
These observations apply to the combined hashes above, not all UI flows or other firmware versions.
The owner reports additional bugs and will raise them in another thread. This record does not classify or resolve those unspecified bugs.
Source changes remain local, uncommitted and unpushed. Replacement PR creation and referenced closure of PRs #2 and #3 remain pending delivery approval.

## Resume, native progress and bounded styling review, 2026-10-31

[HOST-VERIFIED, NOT INSTALLED] The owner authorizes integrating the separate timestamp fix and adding native progress tracking.
This orb first restores the preceding combined controller/Search working tree from its Changes capture.
It then downloads the timestamp thread's authored adapters, tests and validation record into a separate temporary directory.
Function-level integration preserves the newer Search, controller, collection, font and playback-return changes.
The full build regenerates both upstream patches from the combined adapters, not the timestamp thread's older exports.
Source remains uncommitted and unpushed. No PR changes or console access occur.

### Imported startup-resume fix

The source thread is [the timestamp investigation](https://ampcode.com/threads/T-01a19233-98ca-76e7-9df0-791eb654691f).
Its standalone build passes 62 host tests and signed-container integrity inspection, without console installation.
That earlier native hash is `ae3b3a40de0b89c93608b6e9f84db04fd4c5a4217c9423e270530d9e2fb8593f`.
Its browser bundle hash is `b55311a56574ee509bc4970dc68bd7ef7da1862905f81832af808c960e16f52b`.
Those hashes identify the separate candidate, not this combined build.

The imported fix reads live player parameters because history still describes the preceding route during media-source interception.
An explicit positive timestamp takes priority over percentage progress. Start over uses zero.
Percentage conversion requires a positive duration. Native parsing rejects invalid, negative and nonfinite offsets.
A missing offset resets to zero instead of inheriting the preceding stream's offset.
The combined tree passes all 70 existing host tests immediately after integration.

### EVO to Nuvio progress

The frontend saves the originating profile, PlayerController progress context and an opaque session before closing the browser.
That context retains movie identity or exact video, season and episode identity, plus existing artwork and stream metadata.
EVO samples position and duration during active playback and immediately before stop teardown.
It retains the latest positive position, including backward seeks, and the last usable duration for that session.
The console-local progress endpoint refuses another session and withholds unfinished results.
A new handoff resets measurements. A failed start without a positive sample supplies no progress write.

Before rendering the restored route, the frontend validates the profile, return snapshot and native session.
It rechecks the active profile after the HTTP response and delegates saving to PlayerController's existing progress writer.
That writer preserves the current movie/episode schema, placeholder exclusion, unknown-duration marker and 90% watched threshold.
It queues the existing progress and watched cloud synchronization without introducing live provider scrobbling.
The normal browser-storage bridge flushes the resulting local state to the console.

`make check` passes 71 tests, documentation checks and source-pin/private-artifact checks with `.cache/orb-tools/env` active.
The new regression covers exact episode metadata, profile changes, deleted profiles, expired snapshots, stale sessions and malformed timing.
It also covers failed starts and repeated return decisions. Existing Search and playback-return regressions remain green.
A temporary fixture executes the pinned progress-context, flush, repository-write and local-store implementations through the new bridge.
Seven imports cover distinct profiles and episodes, movie identity, backward position, unknown duration and placeholder exclusion.
At 3239999 of 3600000 milliseconds, the episode remains unwatched. At 3240000 milliseconds, only that episode becomes watched.
The fixture replaces cloud scheduling and unrelated series reconciliation, not the local persistence or completion rules.

A temporary GCC 12.2.0 ASan/UBSan probe executes the adapted query parser, handoff branch, snapshot and take-play function.
It also executes the progress sampler, HTTP response builder and playback-ended transition.
Ten offsets plus missing-offset reset pass, alongside session isolation, backward seek, duration retention and final-report immutability.
Failed starts and requests without a session cannot inherit the preceding report.
The first probe compile fails because its no-op logging macro hides parameter uses under `-Werror`.
Preserving those uses in the probe's disabled logger resolves the harness issue without changing production code.

[LIMITATION] Native samples remain in process memory until Nuvio returns and saves them.
Abrupt title termination or power loss before browser return has no recovery checkpoint.
Unknown duration cannot establish watched completion. Actual startup seeking still requires a usable duration and successful demuxer seek.
No hardware resume, progress, watched-state or cloud-sync result exists for this candidate.

### Time-boxed styling review

The read-only audit has a 20-minute ceiling and covers the pinned CSS, matching screen markup and existing adapters.
It identifies a matching cast-focus conflict in constrained and legacy performance selectors.
Those selectors add an outer rectangular shadow while the avatar already supplies its circular ring.
The same conflict affects episode and recommendation/trailer cards. The adapter removes those cards only from the outer-shadow groups.
Their existing artwork rings, dimensions, navigation and animation policies remain intact.
The owner's actual console performance class remains unmeasured, so this mechanism is not a verified console root cause.

Sign Out explicitly uses full width upstream. The requested presentation change makes only that action content-sized.
Account status and other action rows keep their existing widths.
Two image rules now respect the `hidden` attribute after loading failure, preserving cast initials and recommendation placeholders.
The audit stops without a broad redesign or speculative replacement of remaining remote icon-font consumers.

A Chromium fixture renders actual pinned cast, recommendation, episode and account markup with the newly bundled stylesheet.
Fixture data uses generic portraits and a reserved example email, not owner account data.
DOM checks show no outer cast, episode or recommendation shadow in normal, constrained or legacy modes.
The selected cast photo retains its 4px circular ring. Both failed images compute to `display: none`.
The unfocused Sign Out button measures approximately 216px rather than spanning its account list.
Inspected captures cover selected and unselected cast, long names, missing/failed photos and the compact account action.
These fixture checks do not establish system-browser rendering on firmware 12.70.

The first native-build attempt stops at a CSS adapter anchor that occurs in multiple distinct performance groups.
Narrowing the anchor to the outer-shadow group preserves the separate animation groups and permits the full build.
An initial visual fixture omits the detail theme's parent class and clips Account below its viewport.
Adding the actual theme scope and capturing Account separately resolves those fixture issues.
The first recording attempt opens a blank browser after changing restore mode and then overloads its encoder during compilation.
Explicit restore-mode initialization and a later isolated recording replace that failed capture.

### Combined local build

`. .cache/orb-tools/env; make build` succeeds with `integrity: valid`, build `9ee9a542-nuvio_1031-1613`.
Environment: Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM/Clang/lld 19.1.7.
SDK v0.43, pacbrew v0.39, FFmpeg 7.1.1 and both frontend/native source pins remain unchanged.
The receipt is `build/build.json`. Title identity remains `PPSA99997`, with console-hosted UI and the existing SDK-gated helpers.

| Local artifact | Bytes | SHA-256 |
|---|---|---|
| `eboot.bin` | 35993924 | `879d0aa758b803e564bc08366d74198aca7c7d15f9e391ae5a6e10e7bf04d032` |
| `webui/app.bundle.js` | 3178776 | `18b6e429b8fe8092e4ffdc360a4325e44d4f5fd36659013c6192b10d0f996cc0` |
| `webui/css/bundle.css` | 545529 | `d8dbe16e41e9b57dcced21886fdc5a924528eee83b9f93ac3b1813f7bead303d` |

[PENDING] Obtain explicit installation approval and confirm Nuvio is closed before replacing any console file.
Reconfirm the explicitly supplied PS5Upload address before access. Do not scan.
After approved installation, test Resume, Start over, a second title, two episodes and two profiles.
Check that Circle return updates Continue Watching and that completion marks only the intended episode.
Check cast focus, failed-image fallbacks, compact Sign Out, repeated playback return and repeatable Search.
The previously installed combined candidate remains unchanged. No commit, push, merge or PR closure occurs.

[INSTALLATION-VERIFIED, 2026-10-31 16:24:19 UTC] The owner replies "Closed" to the candidate installation confirmation.
The existing Mac execution thread reconfirms the supplied PS5Upload service and installs build `9ee9a542-nuvio_1031-1613`.
The orb cannot reach the private address directly. That availability attempt times out without any console write.
The Mac validates the archive size, SHA-256 and exact three entries before console replacement.
All original sizes and hashes match the preceding installed combined candidate.
The Mac backs up all three originals, fsyncs them and verifies their bytes before the first upload.
The private backup directory uses mode 0700 and each file uses mode 0600.

Only `/data/homebrew/PPSA99997/eboot.bin`, `webui/app.bundle.js` and `webui/css/bundle.css` change, in that order.
Complete readbacks use 35 native, four JavaScript and one stylesheet chunk, each no larger than 1 MiB.
Stable file stats, exact byte comparisons, sizes and SHA-256 values match all three local artifacts in the table above.
All 118 Mac service requests return HTTP 200, with zero failures or retries.
The Mac preserves the private rollback backups. No application launch, account/settings write, scan or firmware change occurs.
No commit, push, merge or PR closure occurs. Runtime resume, progress, watched-state and styling checks remain pending owner testing.

[OWNER-CONFIRMED ON 12.70] The owner replies "it works!" after the requested resume, Continue Watching and styling checks.
This acceptance applies to installed build `9ee9a542-nuvio_1031-1613`. It does not establish unreported profile-isolation or watched-completion results.
The owner also reports an intermittent mouse pointer, possibly during screen changes.

### Pointer compatibility candidate

The installed index already applies `cursor: none !important` from first paint.
Source inspection finds no later Nuvio cursor rule that overrides this declaration.
The intermittent console pointer remains unreproduced on the host. A system-browser cursor-rendering difference remains a hypothesis, not a verified cause.
The candidate supplies a transparent 16-by-16 PNG cursor with `none` as the fallback, retaining the same selector and controller bridge.
The data URI requires no additional asset or network host.

`make ui` succeeds. Comparing packaged files confirms that only the index cursor declaration changes.
The JavaScript bundle, stylesheet and controller bridge remain byte-identical to the installed candidate.
No native code changes or native rebuild occur.
Chromium decodes the cursor PNG with zero alpha in every pixel.
All visible elements in the real host-rendered login page and its error dialog compute to the transparent cursor.
An isolated fixture checks replacement controls and a dynamically inserted dialog with the built inline cursor policy.
The fixture omits the controller bridge so real mouse clicks can exercise its test controls without controller-focus interception.
These checks do not establish cursor suppression in the PS5 compositor.

| Pointer candidate | Bytes | SHA-256 |
|---|---|---|
| `webui/index.html` | 2776 | `0b703951c719b02275c7867e8090225167dc95cd0b72be6b2e308ebe235ab5f1` |
| Installed baseline index | 2642 | `6198d774053d2eba88ba6021d03a55ef191c45263c0dd648ef0bb1d09359ddc1` |

[PENDING] Obtain fresh closed-app installation approval for this index-only candidate, then verify transitions on PS5.
The installed three-file candidate remains unchanged. No console contact, commit, push or PR change occurs during pointer investigation.

### Dual-stick navigation candidate

The owner asks whether pointer styling affects controls and requests D-pad-style movement from both sticks.
Pointer styling changes only the cursor image. Existing pointer-event interception and button handlers remain intact.
The next candidate combines that styling with native stick forwarding, superseding the index-only installation proposal above.

The adapter reuses EVO's existing `scePadReadState` fields, pad masks and `evo_input` repeat implementation.
No new platform declaration, offset or browser Gamepad mapping supplies input.
While the browser is active, either stick supplies one arrow direction beyond a 70-unit dead zone around centre 128.
The dominant axis determines direction. Horizontal wins ties, and the left stick takes priority if both sticks move.
The physical D-pad remains browser-owned. Native playback, IME and stick-click behavior retain their existing handlers.
The frontend sends standard arrow-key down/up pairs to the current focused modal or screen control.
New counters coalesce delayed repeats and discard stale navigation after backgrounding or failed requests.

The extended existing controller regression passes all four arrow mappings, numeric-key compatibility, modal isolation and repeated-report suppression.
It also checks delayed-repeat coalescing, invalid directions and background/reconnection baselines.
All 71 host tests pass. Existing Search and primary-button tests remain green.
A temporary ASan/UBSan probe compiles the generated native stick block with EVO's actual repeat implementation and pad-mask declarations.
It passes both sticks, positive/negative dead-zone boundaries, held-repeat timing, release, dominant diagonals and simultaneous-stick precedence.
The first probe attempt precedes native-source adaptation and cannot find the new block. Running it after adaptation succeeds.

Host Chromium runs the actual bundled frontend with a simulated `/evo/controller` response source.
New right/left reports move the real controller dialog focus from Player settings to Cancel and back.
Inspected dialog crops and a frame-by-frame recording confirm those states without visible pointer artifacts.
The recording contains no owner data or login codes. This simulation does not establish physical stick delivery on PS5.

`. .cache/orb-tools/env; make build` succeeds with `integrity: valid`, build `9ee9a542-nuvio_1031-1643`.
Environment remains Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM/Clang/lld 19.1.7.
SDK v0.43, pacbrew v0.39, FFmpeg 7.1.1 and the source pins remain unchanged. The receipt is `build/build.json`.

| Combined pointer/stick artifact | Bytes | SHA-256 |
|---|---|---|
| `eboot.bin` | 35994244 | `37bf9ddc856761fc795a9f0b1103e74f2b8dfac0f6fccb1e8459d13907824893` |
| `webui/app.bundle.js` | 3179131 | `eddb4435b381a1b568d04fb13c796aaf0469e19cbeb602367881951738e0c41a` |
| `webui/index.html` | 2776 | `0b703951c719b02275c7867e8090225167dc95cd0b72be6b2e308ebe235ab5f1` |
| Unchanged `webui/css/bundle.css` | 545529 | `d8dbe16e41e9b57dcced21886fdc5a924528eee83b9f93ac3b1813f7bead303d` |

[PENDING] Obtain fresh closed-app approval before replacing the native, JavaScript bundle and index, with backups and full readback verification.
Then test both sticks, held movement, neutral drift, diagonals, D-pad, X/Circle, Search/IME and playback return on PS5.
Confirm pointer suppression across screen changes separately. No console contact, installation, commit, push or PR change occurs in this batch.

[INSTALLATION-VERIFIED, 2026-10-31 16:52:21 UTC] The owner confirms Nuvio is closed and clarifies that "push" means console installation, not Git delivery.
The Mac execution thread reconfirms the supplied PS5Upload service and installs build `9ee9a542-nuvio_1031-1643`.
Archive validation confirms exactly the native, JavaScript bundle and index entries, with matching sizes and SHA-256 hashes.
All three installed originals match the expected 1613 baseline, including the unchanged 2642-byte index.
The Mac fsyncs and rereads all three private backups before the first upload.
Backup directories use mode 0700 and files use mode 0600. The Mac preserves the rollback copies.

Only `/data/homebrew/PPSA99997/eboot.bin`, `webui/app.bundle.js` and `webui/index.html` change, in that order.
Complete readbacks use 35 native, four JavaScript and one index chunk, each no larger than 1 MiB.
Each readback matches the candidate bytes, size and SHA-256 in the table above, with stable file stats.
All 118 service requests return HTTP 200. No failure, retry or partial installation occurs.
The stylesheet receives no write or fresh hash check in this installation.
No app launch, account/settings write, scan, firmware change, commit, Git push or PR change occurs.
Physical dual-stick movement and pointer suppression remain pending owner testing on firmware 12.70.

[FAILED ON 12.70] The owner reports that build `9ee9a542-nuvio_1031-1643` brings the mouse pointer back fully.
The transparent-cursor host results do not establish console suppression and do not resolve the reported bug.
Cursor styling and native stick forwarding changed together, so this report does not isolate which change activates the visible system pointer.
The next local candidate restores the previous `cursor: none !important` declaration while retaining the stick implementation.
This index-only rollback isolates the cursor change. It does not claim to fix the original intermittent pointer.
Its index matches the previous 2642-byte baseline, SHA-256 `6198d774053d2eba88ba6021d03a55ef191c45263c0dd648ef0bb1d09359ddc1`.
`make ui` succeeds and all 71 host tests pass. Host Chromium computes `cursor: none` on all 25 visible login-page elements.
This host check does not qualify the PS5 pointer overlay.
No native code changes or native rebuild occur. The full 1643 package and its receipt still identify the earlier build, not this UI-only rollback.
[PENDING] Obtain closed-app approval before backing up and replacing only `webui/index.html`.
Then compare D-pad-only navigation with each stick, noting whether the pointer appears before either stick moves.
No console contact, replacement, commit, Git push or PR change occurs during rollback preparation.

[ROLLBACK-VERIFIED, 2026-10-31 16:58:09 UTC] The owner confirms Nuvio is closed and authorizes the index-only replacement.
The Mac reconfirms PS5Upload availability and verifies the installed 2776-byte index against the recorded 1643 hash.
A private local backup precedes the only upload. The Mac flushes, fsyncs and rereads the backup to verify its bytes.
The backup directory uses mode 0700 and its file uses mode 0600.
The restored 2642-byte index matches SHA-256 `6198d774053d2eba88ba6021d03a55ef191c45263c0dd648ef0bb1d09359ddc1`.
Complete console readback matches its bytes, size and hash, with stable regular-file stats.
All 11 service requests return HTTP 200, with zero failures or retries.
The 1643 native and JavaScript files remain installed. No native, JavaScript, stylesheet or other console file receives a write.
No app launch, account/settings write, scan, firmware change, commit, Git push or PR change occurs.
[PENDING] Owner compares D-pad-only navigation and each stick after relaunch to isolate pointer behavior.

### Lost-login report and read-only recovery assessment

[REGRESSION REPORTED ON 12.70] The owner reports lost login after the index rollback and relaunch.
The investigation makes no console write, account change or backend authentication request.
The Mac reads only the browser-storage directory and two bounded 256 KiB log tails through PS5Upload.
It preserves the current storage snapshot in a private local directory, with fsync and reread verification.
No raw storage, tokens, account identifiers or owner configuration enter this repository.

The sole current storage file is valid JSON with five entries, an anonymous-session flag and no profile-related keys.
Both token fields are nonempty, but they belong to the anonymous-session snapshot, not a verified restored owner session.
Its size is 1136 bytes. The saved access-token expiry is in the future at inspection, without a server-validity check.
Recent logs show a successful 884985-byte storage save followed by a successful two-byte save.
Subsequent openings serve two-byte restores, followed by small saves and another two-byte save.
The historical two-byte bodies are unavailable. The source permits an empty object to replace the complete saved state.
Browser origin, configured storage origin and Nuvio hook selection remain unchanged across the two parsed recent openings.
The first observed empty write precedes the first 1643 build marker in the retained log summary.
This bounded evidence does not establish the write's cause or its relationship to closure, refresh or the cursor rollback.

Fifteen read-only service requests return HTTP 200. An initial local compressed-response decoding failure requires a corrected root fetch.
No console write or partial installation occurs. Raw log tails are not retained, limiting reconstruction of surrounding events.
The Mac also verifies and privately preserves an already-downloaded earlier browser snapshot without another console or backend request.
That valid 871690-byte snapshot contains 45 entries, nonempty account-token fields, no anonymous flag and four profiles with a matching active selection.
Its access-token expiry is in the future at inspection. Server acceptance and refresh-token usability remain untested.
The snapshot dates from earlier that day and lacks `collectionsState`. It is not a complete or current configuration backup.

[PENDING] Obtain explicit closed-app approval before restoring any account-bearing snapshot.
Disclose that recovery can revert newer local settings or progress. Preserve the current state before any approved replacement.
Do not claim the login-loss cause or a persistence fix from these observations alone.

[RECOVERY DECLINED] The owner chooses to sign in manually. Do not restore the saved session or change account data.
The owner also observes the pointer on the QR screen after the cursor rollback.
This confirms that the remaining pointer problem is not limited to content cards or detail-screen transitions.
It does not establish whether the pointer appears before any analog-stick movement.

A bounded source check finds no documented pointer-disable flag in the browser declarations used as EVO's layout reference.
The inspected [SharpProspero browser bindings](https://github.com/SvenGDK/SharpProspero/blob/5dfdb4b0b166e83dc9ae275001afb695f12c7174/src/SharpProspero/Interop/Dialog/WebBrowserDialog.cs)
expose `Control` as an unsigned field without named bit values or a pointer-hiding declaration.
The platform wrapper and the pinned payload SDK headers provide no verified pointer-disable control for this investigation.
This does not prove that no such control exists. No guessed control bits, new API declarations or additional CSS workarounds are introduced.
No console contact, installation, account restoration, commit, Git push or PR change occurs during this source check.
[OWNER OBSERVATION] The owner confirms that the pointer appears before touching either stick after launch.
Stick movement is therefore not a necessary trigger. This observation does not isolate the stick-support code or establish the pointer's cause.
The console installation and input mappings remain unchanged. The pointer problem remains unresolved.

### Combined-candidate review corrections, 2026-10-31

[HOST-VERIFIED, NOT INSTALLED] The owner authorizes corrections for both behavioral review findings and the Triangle instruction.
Both native progress sampling paths now skip uncommitted scrub previews. They retain the last measured playback position.
Search mount passes its navigation context to the keyboard adapter, which ignores automatic requests during back navigation.
Explicit Triangle and textbox requests remain available. The browser still closes before native IME entry.
The beginner guide now identifies Triangle as Search rather than the controller menu.

Before correction, the Search regression makes an unexpected keyboard request during back navigation.
The native regression reports the 950-second scrub target instead of the last measured position, 890 seconds in a 1000-second title.
Both regressions pass after correction. The native test also saves a real later 920-second position, above the watched threshold.
Its first host compilation fails because the C bridge's `isfinite` name needs a C++ namespace import in the harness.
Adding `using std::isfinite` corrects the harness only, before the behavioral before/after checks.
`make check` passes all 72 tests, with zero hard documentation findings. Source pins and private-artifact checks pass.

A Chromium DOM check executes the generated Search mount, result action, detail Back and native-keyboard adapter with stubbed services and renderer.
Fresh Search requests input once. Result-detail Back requests input zero times and retains the `Arrival` query and result surface.
Explicit textbox activation then requests input once. This checks navigation-context wiring, not actual console IME execution or full-screen rendering.
The temporary browser session and local supervised service stop after the check.

`. .cache/orb-tools/env; make build` succeeds with `integrity: valid`, build `9ee9a542-nuvio_1031-1854`.
Environment: Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM/Clang/lld 19.1.7.
SDK v0.43, pacbrew v0.39, FFmpeg 7.1.1 and source pins remain unchanged. The receipt is `build/build.json`.
The build regenerates both reviewable upstream patches.

| Local review-fix candidate | Bytes | SHA-256 |
|---|---|---|
| `eboot.bin` | 35994308 | `fc60832c2ecd2ab6a40bc896f09140528d7c4f14084fba9528e253cea3782f6c` |
| `webui/app.bundle.js` | 3179156 | `d580e1e4284572ba6c572cb2e3eb86819bdd2e41fa8282a9371ae516c7603535` |
| Unchanged `webui/css/bundle.css` | 545529 | `d8dbe16e41e9b57dcced21886fdc5a924528eee83b9f93ac3b1813f7bead303d` |
| Unchanged restored `webui/index.html` | 2642 | `6198d774053d2eba88ba6021d03a55ef191c45263c0dd648ef0bb1d09359ddc1` |

[PENDING] Test scrub-preview cancellation across the 90% threshold and Search-result Back on PS5 after an approved installation.
No console contact, installation, account change, commit, Git push or PR change occurs in this correction batch.
The current console installation remains unchanged. Pointer suppression and the earlier login-loss cause remain unresolved.

[INSTALLATION-VERIFIED, 2026-10-31 19:01:18 UTC] The owner authorizes installation and confirms Nuvio is closed.
The Mac runner stages and verifies the two 1854 candidates from the table above.
The initial availability request returns HTTP 403. That attempt makes no console file read or write.
A bounded direct-access diagnostic returns HTTP 200 for the root and token endpoints, without redirects or proxies.
The earlier denial's cause remains unknown. The diagnostic does not upload files.

The resumed installation reconfirms availability and fully reads both originals, which match the recorded 1643 native and JavaScript baselines.
Both originals have private local backups before the first upload, with mode 0700 directories and mode 0600 files.
The Mac flushes, fsyncs and rereads each backup file. It does not record a backup-directory fsync.
The backup-complete event occurs at 19:01:04 UTC, before either upload-begin request.
Only `/data/homebrew/PPSA99997/eboot.bin` and `webui/app.bundle.js` change, native first.
Full readbacks use 35 native chunks and four JavaScript chunks, each no larger than 1 MiB.
Both installed files match the 1854 table's exact bytes, sizes and SHA-256 hashes, with stable regular-file fingerprints.
The resumed installation makes 102 requests, all HTTP 200, with zero failures or retries.
These counts exclude the earlier one-request denial and two-request successful diagnostic.
No partial-install uncertainty remains. CSS, the restored `cursor:none` index and account/storage files receive no write.
No app launch, account restoration, scan, firmware change, commit, Git push or PR change occurs.
[PENDING] Owner tests Search-result Back and scrub-preview cancellation on the installed 1854 build.
Installation verification does not establish those runtime behaviors. The pointer issue remains unresolved.

### Search-to-Home return correction, 2026-10-31

[OWNER-VERIFIED ON 12.70] On installed 1854, result-detail Back restores Search without reopening the keyboard.
[REGRESSION REPORTED] The owner cannot return Home afterward. Scrub-preview cancellation remains unconfirmed on console.

A Chromium check reproduces the loop using the generated router, Search, detail and keyboard methods with real browser history and DOM.
It stubs data services and rendering, not the history-return methods.
Detail Back replaces the page with Search but retains Search as the logical predecessor.
The next Back stays on Search. The earlier host check stopped before this second Back and missed the failure.
An extended regression test also fails before correction, expecting Home but observing Search.

The PS5 detail adapter now uses the existing `Router.popToExistingRoute("search", {})` before its replacement fallback.
The router's pending-return handler removes the retained Search entry before generic popstate suppression can interfere.
Overlay dismissal and no-history fallback keep their existing owners. Other platforms keep their previous detail-return behavior.
After correction, the same Chromium journey reaches Home from both recreated Search and Home-origin Search.
Both retain the `Arrival` query on the intermediate Search page and make no additional automatic keyboard request.
An initial after-check loads cached pre-fix JavaScript and reproduces the old failure.
The harness then fetches modules with `cache: "no-store"` and confirms both corrected journeys.
This is a host history/DOM check, not physical PS5 input or IME execution. The temporary browser and service stop afterward.

`make check` passes all 72 tests. `make ui` succeeds, and the Nuvio upstream patch regenerates through `scripts/patches.py`.
Environment remains Linux x86-64, Python 3.13.7 and Node.js 22.23.2, with unchanged source pins.
The JavaScript-only candidate is `build/ui/app.bundle.js`, 3179241 bytes,
SHA-256 `3333661e0e2988037ace3e3d236b120b135e9a8a8ef1d670ed8c922f85a3bb95`.
CSS and index hashes match the installed baselines. No native source changes or native rebuild occur.
The packaged 1854 title and its receipt still describe the preceding JavaScript bundle, not this UI-only candidate.
[PENDING] Obtain fresh closed-app installation approval, then back up and replace only `webui/app.bundle.js` with full readback verification.
No console contact, account change, installation, commit, Git push or PR change occurs in this correction batch.

[INSTALLATION-VERIFIED, 2026-10-31 19:14:54 UTC] The owner confirms Nuvio is closed and authorizes the JavaScript-only correction.
The Mac reconfirms PS5Upload availability with direct access, disabled redirects and no proxies.
The installed original matches the 3179156-byte 1854 baseline, SHA-256 `d580e1e4284572ba6c572cb2e3eb86819bdd2e41fa8282a9371ae516c7603535`.
A private backup precedes the upload, with mode 0700 directory and mode 0600 file.
The Mac flushes, fsyncs and rereads the backup, then rechecks the installed baseline fingerprint before writing.
Only `/data/homebrew/PPSA99997/webui/app.bundle.js` changes.
Four full readback chunks match the 3179241-byte candidate and SHA-256 `3333661e0e2988037ace3e3d236b120b135e9a8a8ef1d670ed8c922f85a3bb95`.
Each chunk is at most 1 MiB. Stable regular-file fingerprints and byte-for-byte equality confirm the complete replacement.
All 17 console requests return HTTP 200, with zero failures or retries.
Native, CSS and the restored `cursor:none` index receive no write. Account/storage files receive no read or write.
No app launch, login restoration, scan, firmware change, commit, Git push or PR change occurs.
[PENDING] Owner tests detail to Search to Home on the installed JavaScript correction. Host checks do not establish console navigation behavior.

[OWNER-VERIFIED ON 12.70] The owner confirms the instructed Search to details to Search to Home flow works after this JavaScript installation.
This confirms the successive Circle returns without unsolicited keyboard reopening for that flow.
Scrub-preview cancellation, physical stick navigation and pointer suppression do not gain new console evidence from this confirmation.

## Home-screen background and music, 2026-10-31

[SOURCE-VERIFIED] This candidate includes the latest uncommitted controller, Search and playback changes from thread `T-01a192b0-887b-7138-b812-9b82129cb121`.
The imported capture is `cap_01a19364f40377798809ac088a4888e8`, based on commit `45519c5b6d2e8c1998035fd96a8bd09dae866696`.
The candidate retains title `PPSA99997`, source pins and console-hosted UI.

The owner-selected background is the last supplied Gemini cinema-ribbon JPEG, originally 2752x1536.
ImageMagick resizes and centre-crops it to 3840x2160 without a new design pass.
DirectXTex converts that image to single-surface BC7_UNORM DX10 DDS without mipmaps.
Both `pic0.dds` and `pic1.dds` use the same image. PNG counterparts remain available.
The existing tile icon stays unchanged.

The supplied WAV has 40 seconds of 48 kHz stereo, 24-bit PCM audio.
FFmpeg applies -11.53 dB gain and produces 16-bit PCM without changing its duration or fades.
The owner-approved encoder produces 192 kb/s ATRAC9 with whole-track loop metadata.
FFmpeg independently decodes the resulting RIFF file without errors.
The file has 960680 bytes, below the 2097152-byte limit.
Its loop spans 1920000 samples, with 256 samples of encoder-delay compensation.
Decoded loudness measures -28.01 LUFS. The title metadata declares `loudnessSnd0: "-28.00"`.
Audio inspection finds clean ambient music without speech or obvious distortion.
The original fade-in and fade-out remain, so each repeat includes a quiet lull.

The PS5 profile-selection hint now says "Press Square or Options to manage profile".
Other platforms retain their translated hold instruction. Management mode retains its existing selection hint.

[LOCALLY BUILT] Preparation uses Linux x86-64, Wine 8.0, ImageMagick 7.1.2-25 and host FFmpeg 5.1.9.
The native environment uses Python 3.13.7, Node.js 22.23.2 and LLVM 19.1.7.
SDK v0.43, pacbrew v0.39 and target FFmpeg 7.1.1 remain pinned.

| Input or prepared media | SHA-256 |
|---|---|
| Supplied JPEG | `781709b2d147fc2c5155485026eabd7c46ea3adb39657d418efbf0fd5f7b9b23` |
| Supplied WAV | `d4f4cc41f529b941385f9a23ff04fa48d7722b8267bcf5f6bf29876baa8b20ec` |
| Prepared `assets/launch.png` | `cfb06aa5c23cd5c582acb838ac66e8ac0a8d2a0a83983b5f8b9735a3eeecbe31` |
| Prepared `assets/launch.dds` | `0a6fad7b3551c720e6a2db76893b30da7b32d6f2396b73a5553a64d26e2e0ab1` |
| Prepared `assets/snd0.at9` | `e6f759ccca6db6fbf82351933d0f69d02ff80fa969ecef4eeceb633b8b9a613f` |
| DirectXTex `may2026` texconv | `dcfdec10244e02cf5037fba089c55fb7e1326b1c8181742d77d15fa5cb5eef06` |
| AT9 and AT3 Converter 2.7 archive | `4b4e2c598a60fa0447c1b67423443a4d4f58d5133543c79dc1d1f9e642c4d383` |
| Locally used PS4 encoder | `8228fbd4ea5552a1ea80ca8304c09104423d142313d6d80ea49d63c048c8d00b` |

Media preparation commands, with temporary paths shortened:

```sh
magick supplied.jpeg -resize '3840x2160^' -gravity center -extent 3840x2160 -strip PNG24:launch.png
wine64 texconv.exe -nologo -y -f BC7_UNORM -m 1 -dx10 -nogpu -o output launch.png
ffmpeg -i supplied.wav -af volume=-11.53dB -ar 48000 -ac 2 -c:a pcm_s16le -map_metadata -1 input.wav
wine PS4_at9tool.exe -e -br 192 -fs 48000 -wholeloop input.wav snd0.at9
ffmpeg -i snd0.at9 -c:a pcm_s16le decoded.wav
```

An initial loop check incorrectly expects zero-based RIFF loop points and fails.
The corrected check reads `fact` encoder delay and verifies the complete 40-second span after compensation.
The rendered Chromium profile picker at 1920x1080 shows the new instruction without clipping or overlap.
Two local fixture profiles avoid account access during this check.
The existing layout overlaps title and subtitle at 1280x720. This label change does not repair that unrelated layout.

The prepared DDS passes dimension, DX10 format, surface, mip-count and exact file-size checks.
It has 8294548 bytes. DirectXTex decodes it back to PNG for visual inspection.
The decoded artwork retains the dark left area and the supplied right-side cinema ribbon without visible corruption.

[LOCALLY BUILT] The complete title builds as `9ee9a542-nuvio_1031-1935` with signed-container `integrity: valid`.
The independently authored runtime retains its pinned hash.
The receipt covers 240 title files and eight unstripped helpers.
The store ZIP passes integrity checks and matches every receipt hash.
Its media matches the selected source bytes, and the browser bundle contains the corrected profile hint.
The title still serves its own browser UI and embeds promotion for loader port 9021.

`make check` passes all 72 tests, documentation checks and source/private-artifact checks.
The documentation checker reports 35 advisory findings and zero hard violations.
`git diff --check` passes.

```sh
. .cache/orb-tools/env
NUVIO_WORK_DIR="$PWD/build/presentation" make build
make check
NUVIO_WORK_DIR="$PWD/build/presentation" make release
```

| Candidate artifact | SHA-256 |
|---|---|
| `PPSA99997.zip`, 54751642 bytes | `c9f1e3732f558b750c002fc0de6db177f842838e11c97d5930857d65398efa43` |
| Signed `eboot.bin` | `3389fd3fff2700f0dec2ceaec271e14d5c58f9aec6dec54708067d0682c44021` |
| Runtime `sce_module/libc.prx` | `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036` |
| Browser `webui/app.bundle.js` | `f88bd82f891863d7d56cc66180c41ccbfc37f8174e91742f4e4500ca62f86cf5` |

The receipt and local package use the existing alpha.7 version and title identity.
This is a private test candidate, not a newly published release.

[UNKNOWN] This package has no new console execution result.
Selection artwork, launch artwork, music playback, repeat behavior and Shell caching need a console test.
Host image and audio inspection do not establish PS5 Shell behavior.
No console address, scan, installation, firmware change, commit, push or release publication occurs during preparation.

### Combined package installation

[INSTALLATION-VERIFIED] The established Darwin/arm64 Mac executor reports completion at 2026-10-31 19:46:51 UTC.
The owner authorizes the full package installation and confirms Nuvio is closed.
Closure relies on that confirmation, not an independent unmount check.
The console's previously owner-reported firmware is 12.70. This installation does not query firmware or resident support-stack versions.

Before writing, the executor verifies the ZIP hash, size, CRCs, safe unique paths and complete 240-file receipt inventory.
All four critical installed baselines match the preceding native, JavaScript, CSS and index records.
Four existing files need replacement: `eboot.bin`, `webui/app.bundle.js`, `sce_sys/pic0.png` and `sce_sys/pic1.png`.
Three files are new: `sce_sys/pic0.dds`, `sce_sys/pic1.dds` and `sce_sys/snd0.at9`.
The remaining 233 files already match, including the metadata, CSS and index.

All four originals receive private Mac backups before the first upload.
Backup directories use mode 0700 and files use 0600. Flush, fsync and reread checks verify each backup.
The executor rechecks regular-file fingerprints and fully verifies every replacement using reads of at most 1 MiB.
It then rereads all 240 installed files and matches every receipt hash again.
Existing file modes remain unchanged.
Installed eboot has 35994308 bytes and SHA-256 `3389fd3fff2700f0dec2ceaec271e14d5c58f9aec6dec54708067d0682c44021`.
Installed JavaScript has 3179310 bytes and SHA-256 `f88bd82f891863d7d56cc66180c41ccbfc37f8174e91742f4e4500ca62f86cf5`.

All 1889 requests return HTTP 200: one root, one token, 1218 stat, 655 read and 14 upload requests.
There are zero failures, retries, deviations or partial replacements.
Private preflight and installation evidence stays with the Mac backups, outside Git.
No `/data/nuvio/`, account/storage file, Shell database or cache receives access.
No unrelated deletion, launch, firmware change, commit, push or publication occurs.

[UNKNOWN] Installation verification does not establish runtime execution or visible Shell presentation.
The owner still needs to check highlighted-title artwork, music, repeat behavior and startup.

## Media classification and fork identity, 2026-10-31

[OWNER-REPORTED ON 12.70] The owner reports that a ShadowMount remount makes the preceding presentation changes visible.
The owner confirms firmware 12.70 and requests native Media classification and a separate app ID.
This report does not independently verify music playback, loop behavior or the new Media classification.

[SOURCE-VERIFIED] The PS5 developer wiki documents `applicationCategoryType: 65536` as a native Media app and badge `2` as non-game.
Source: <https://www.psdevwiki.com/ps5/Param.json>.
The source metadata now declares those values. The adapter copies both rather than inheriting EVO's Games classification.

The fork selects `PPSA99996`, with matching content ID, concept ID, title paths, process matching and generated controls.
The build remaps both inherited vendor identities without modifying the attributed vendor source.
Persistent settings remain under `/data/nuvio/`. The new ID creates a separate title, not an in-place update.
Never run both versions together. Keep the old installation until the new title works.

[SOURCE-VERIFIED] The inspected `darkxex/ps5-homebrew-catalog` lists `PPSA99997` under Bilawal Riaz's original PS5 port.
Its app inventory has no `PPSA99996` record at inspection. Exact-ID web searches find no existing use.
This is not proof of global uniqueness, a Sony assignment or a community reservation.
The catalog accepts reservation pull requests, but its derivative-app policy also requires substantial differences and a distinct name.
Source: <https://github.com/darkxex/ps5-homebrew-catalog/blob/main/docs/submitting.md>.
No remote reservation, listing, commit, push or publication occurs.

The README credits Bilawal's port, Nuvio TV and EVO Player and explains the separate testing and release workflow.
The referenced development thread contains no evidence of upstream rejection. The README does not claim rejection or rule out future upstream contributions.

[HOST-TESTED] `make check` passes all 72 tests with the configured orb toolchain, including rejection of the upstream ID by promotion and close helpers.
An initial run without `.cache/orb-tools/env` selects GCC and fails on an existing misleading-indentation warning in `promote.c`.
Using the configured LLVM toolchain resolves that environment mismatch without changing the unrelated code.
Documentation checks report zero hard violations. `git diff --check` passes.

The first native build stops at EVO's explicit Games-only metadata validator.
The adapter now requires exactly category `65536` and badge `2` instead, retaining the other validation rules.

[LOCALLY BUILT] The corrected build succeeds as `9ee9a542-nuvio_1031-2000`, with signed-container `integrity: valid`.
The environment remains Linux x86-64, Python 3.13.7, Node.js 22.23.2 and LLVM 19.1.7.
SDK v0.43, pacbrew v0.39 and target FFmpeg 7.1.1 remain unchanged.
The receipt matches all 240 title files and eight unstripped helpers.
The native title and every helper contain neither old title ID. Generated controls contain only the new identity.
The music and DDS assets match the preceding installed presentation candidate byte-for-byte.

Executing the generated packaging validator accepts the native Media pair.
It rejects Games, both mixed category/badge pairs and a mismatched content ID.
The complete build, `make check`, `make release` and receipt verification succeed with the configured orb environment.

| New candidate artifact | SHA-256 |
|---|---|
| `PPSA99996.zip` | `dc018f70ad514cf83b7ab724c35e360b103379083270034957574b32e90bfe07` |
| Signed `eboot.bin`, 35994308 bytes | `2df1e879954b026b7de12ab37f6fe99acb80adb49aca78d4ea86408c0a9ec0d2` |
| `sce_sys/param.json`, 915 bytes | `6397a30641f3f31421d8303578aa6219a768563ed0749941a9b4164c6099c127` |

[PENDING CONSOLE TEST] These checks establish compilation and package contents, not console execution.
Media placement, launch, native playback and presentation on firmware 12.70 need console validation of this exact new title.
No console connection, installation, deletion, remount or Shell database/cache write occurs during this change.

### Separate Media title installation

[INSTALLATION-VERIFIED] The established Darwin/arm64 Mac executor reports successful installation at 2026-10-31 20:07:54 UTC.
The owner explicitly authorizes installation. The executor confirms `/data/homebrew/PPSA99996` is absent before creating the separate title.
It creates 23 required directories and 240 new files, with zero overwrites or deletions.

Before writing, the executor verifies archive size, SHA-256, CRCs, unique safe paths, absence of symlinks and the exact receipt inventory.
The archive has 54751574 bytes and SHA-256 `dc018f70ad514cf83b7ab724c35e360b103379083270034957574b32e90bfe07`.
The receipt SHA-256 is `f315d92a39f70bed57c1e034fa1555c94ecabd17a411b04d8d56eefda04915be`.
Every upload receives complete raw readback verification in chunks of at most 1 MiB with stable regular-file stats.
A second complete readback matches all 240 receipt hashes again.
Installed eboot and metadata hashes match the preceding candidate table.
The installed metadata declares `applicationCategoryType: 65536` and `contentBadgeType: 2`.
An initial diagnostic uses incorrect field labels, not incorrect package values. The executor verifies the actual fields afterward.

All 2638 requests return HTTP 200: two root, two token, 1517 stat, 23 mkdir, 480 upload and 614 read requests.
The executor reports zero failures, retries or partial installation.
Private evidence remains on the Mac in `nuvio-media-2000-private-f4_dcksw`, with directory mode 0700 and file mode 0600.
Evidence includes `preflight-evidence.json`, `verified-uploads.jsonl` and `installation-evidence.json`.

The executor does not access or modify the old title or `/data/nuvio/`.
No app launch, close, payload, remount, Shell database/cache write, automatic rollback or Git action occurs.
Current old-title closure remains unknown. The owner must refresh ShadowMount manually.
[UNKNOWN] Registration, Media placement, artwork/music and runtime execution still need console verification.

## Initial fork release consolidation, 2026-10-31

[OWNER-REPORTED ON 12.70] Highlighting the Games title plays its selection music. Highlighting the Media title does not.
The installed candidates contain identical audio. This observation does not establish behavior for every PS5 Media app.
The owner requests Games classification again. New metadata uses category `0` and badge `1`, retaining `PPSA99996`.

[SOURCE-VERIFIED] The QR login request takes its device label from the platform adapter.
The PS5 runtime now supplies `PS5` instead of `Web Browser`, including device-session metadata.
Other browser runtimes retain their existing labels. Existing registered sessions may retain their previous names.
[HOST-TESTED] A Node harness executes the actual patched adapter, QR `startRpc`, authentication request method and device-metadata resolver.
It verifies the PS5 request name and metadata, with an ordinary-browser control. It makes no network or backend login requests.

[HOST-TESTED] Review identifies two playback-progress failures and the combined candidate corrects both.
A failed native-report fetch or progress write remains retryable, including after browser recreation.
A committed seek to zero no longer imports an earlier near-end sample. Zero-duration teardown does not erase a valid sample.
Host regression cases cover these paths, profile/session isolation and uncommitted scrub previews.

[HOST-TESTED] The Mac investigation reproduces failed or empty lifecycle reads posting `{}` through the unchanged storage hook.
Its bounded console-log inspection places a two-byte overwrite before the observed Media startup, not after it.
The exact console event remains unknown. This evidence does not attribute data loss to the title category.
No recovery or console write forms part of this investigation.

The corrected hook rejects failed and incomplete snapshots, tracks explicit removals, and validates restored data before enabling saves.
Explicit sign-out and reset can still save empty state. A failed restore disables saving for that document.
Only acknowledged synchronous loopback POSTs advance the saved baseline. Failed transports remain retryable.
Nine storage tests execute the emitted hook with synthetic values. The unchanged hook fails eight cases. The corrected hook passes all nine.

[LIMITATION] Synchronous storage requests can block the browser. Teardown rejection retains the previous disk state, not necessarily the latest changes.
The native file writer remains in-place, not crash-safe or transactional. Another writer can still replace state.
Standard Storage API mutations are the inspected frontend contract. Console WebKit behavior needs validation.

[HOST-TESTED] Configured `make check` passes all 81 tests, with 36 advisory documentation findings and zero hard violations.
Source-pin and private-artifact checks pass. `git diff --check` passes.
The configured toolchain avoids the previously recorded GCC warning failure without modifying that unrelated code.

The README contains the AI-use disclosure directly. The cleanup removes redundant startup and announcement pages after preserving their useful content.
Build instructions, source attribution, release procedure and historical validation evidence remain available.

[LOCALLY BUILT] `NUVIO_WORK_DIR="$PWD/build/presentation" make build` succeeds as `9ee9a542-nuvio_1031-2031`.
The signed container reports `integrity: valid`. The receipt matches the exact 240-file title inventory and eight unstripped helpers.
The title and all helpers contain neither inherited title ID. The packaged metadata declares Games classification and `PPSA99996`.
The environment remains Linux x86-64, Python 3.13.7, Node.js 22.23.2, LLVM 19.1.7, SDK v0.43, pacbrew v0.39 and FFmpeg 7.1.1.
`make release` succeeds. Both ZIPs pass CRC, unique-path and safe-path checks. No console action occurs.

| Combined candidate artifact | Bytes | SHA-256 |
|---|---:|---|
| `PPSA99996.zip` | 54751833 | `c57e5e05fabc85524700464c46f9ed853ed94c3520ea78968fd190bee8d1bf88` |
| `eboot.bin` | 35994308 | `bcc399d085767389d33351a7cdc1a6a573afe1d8dbb00165c31605c5fa676279` |
| `webui/app.bundle.js` | 3179563 | `cc4980811550125f0ac19980b5e2b422008b8b3176a52a537d70553fe82ad08c` |
| `sce_sys/param.json` | 911 | `f6a92cc9399c354a99b0fcd8cf4aa3fc41649d34ce39979de57ef4531db5c1f3` |

[PENDING CONSOLE TEST] This exact combined candidate still needs QR-label, storage, controller, playback and selection-music validation on hardware.

## Workflow and cache improvements, 2026-10-31

[SOURCE-VERIFIED] CI now runs on PR updates and pushes to `main`, not duplicate feature-branch push events.
Superseded check runs cancel. Versioned release runs retain an active publication instead of cancelling it.
Host, documentation and private-artifact checks always run for these CI events.
The existing `check` and `native-linux` status names remain available for branch protection.
The branch reports protection, but the token cannot read its detailed rules. No protection settings change.

Documentation-only ranges skip compilation. Mixed PRs can reuse a successful build record for the same non-Markdown Git tree.
Missing or cancelled build records require another build. A stable final gate rejects failed checks, failed builds and unverified skips.
The shared Linux workflow builds both PR candidates and versioned packages with LLVM 19.
Manual Release runs upload downloadable artifacts without publishing, including when selected on a tag.
An optional manual macOS compatibility build uses separate caches and artifacts. Only Linux artifacts enter versioned releases.
Publishing jobs receive write permission, recheck checksums and preserve existing release assets on reruns.

Downloaded archives, compiled FFmpeg and npm downloads use separate caches.
Archive checksums remain mandatory. FFmpeg cache identity includes its source, SDK and pacbrew pins, LLVM version and flags.
The new LLVM 19.1.7 cache ID is `b552904bcd83202b`, replacing the older identity once.
Four host regressions cover relevant-input invalidation, unrelated-edit stability and cached installation reuse.

[HOST-TESTED] Checksum-verified actionlint 1.7.7 accepts all three workflows.
Disposable probes execute the actual change-detection Python and publication/package shell blocks extracted from the YAML.
Synthetic Git commits cover documentation changes, mixed PRs, missing bases, renames, deletions, binary/tabbed paths and version changes.
The stable native gate passes successful builds and verified skips, but rejects failures, cancellations and unverified skips.
Fake GitHub transport probes verify draft/PR flags, exact target commits, rerun preservation and rejection of tampered packages before publication.
PR, manual and version-tag packaging probes verify repository, tag and artifact outputs. No probe publishes or triggers a workflow.
An initial fake-transport probe fails because its release-view stub cannot observe its preceding simulated create.
Correcting that fixture makes all probes pass without a workflow change.

[HOST-TESTED] Configured `make check` passes 85 tests. Source-pin and private-artifact checks pass.
Documentation checks report 36 advisory findings and zero hard violations. `git diff --check` passes.

[LOCALLY BUILT] A cold build with the new cache identity succeeds as `9ee9a542-nuvio_1031-2050`, with signed-container `integrity: valid`.
The exact receipt matches 240 title files and eight unstripped helpers. `make release` succeeds.
A real warm-cache installation copies FFmpeg without compilation. All five installed library hashes match the cached libraries.
The environment remains Linux x86-64, Python 3.13.7, Node.js 22.23.2, LLVM 19.1.7, SDK v0.43, pacbrew v0.39 and FFmpeg 7.1.1.

| Workflow-build artifact | SHA-256 |
|---|---|
| `PPSA99996.zip` | `ab9041b968f17f12146c6f10c30fb81cc0555298003f70992d710f417d0feb9f` |
| Signed `eboot.bin` | `dcdc9f2006afa5291243cd9b1a1e07e0ef330f2299432ffa63599a75637d96fe` |

[PENDING] The new workflow orchestration and cache hit/miss behavior still need execution on GitHub runners.
Manual macOS and tag-publication paths receive no live trigger during this task. No console action occurs.
