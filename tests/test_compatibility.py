"""Exercise native helper output with synthetic SDK responses, not a PS5."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <sys/types.h>
#include <sys/user.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
uint32_t kernel_get_fw_version(void) { return 0x12700000; }
int sysctl(const int *mib, unsigned count, void *out, size_t *size,
           const void *input, size_t length) {
    (void)mib; (void)count; (void)input; (void)length;
    struct kinfo_proc rows[2] = {{0}};
    for (int i=0; i<2; i++) {
        rows[i].ki_structsize=sizeof(rows[i]);
        rows[i].ki_pid=41+i;
        strcpy(rows[i].ki_comm,"eboot.bin");
    }
    if (getenv("BAD_RECORD")) rows[0].ki_structsize=0;
    if (out) memcpy(out,rows,sizeof(rows));
    *size=sizeof(rows);
    return 0;
}
int sceKernelGetAppInfo(pid_t pid, void *out) {
    static unsigned target_queries;
    unsigned char *bytes=out;
    memset(bytes,0,96);
    if (pid==42 && getenv("QUERY_FAIL")) return -1;
    if (pid==41 && getenv("TARGET_QUERY_FAIL")) return -1;
    if (pid==42 && !getenv("DUPLICATE")) {
        memcpy(bytes+20,"PRIVATE99",10);
        return 0;
    }
    size_t offset=(size_t)atoi(getenv("TITLE_OFFSET"));
    if (getenv("MISSING") || (pid==41 && target_queries++ && getenv("IDENTITY_CHANGED"))) {
        memcpy(bytes+offset,"PPSA99998",10);
    }
    else memcpy(bytes+offset,"PPSA99997",10);
    if (getenv("DOUBLE_TITLE")) memcpy(bytes+40,"PPSA99997",10);
    if (getenv("UNTERMINATED")) bytes[offset+9]='X';
    return 0;
}
'''


class CompatibilityTests(unittest.TestCase):
    def test_reports_layout_without_claiming_permission_compatibility(self):
        compiler = shutil.which('clang') or shutil.which('cc')
        if not compiler:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            headers = {
                'sys/proc.h': '',
                'sys/user.h': 'struct kinfo_proc { int ki_structsize; pid_t ki_pid; char ki_comm[20]; };',
                'sys/sysctl.h': '#include <stddef.h>\n#define CTL_KERN 1\n#define KERN_PROC 14\n#define KERN_PROC_PROC 8\nint sysctl(const int *, unsigned, void *, size_t *, const void *, size_t);',
                'ps5/kernel.h': '#include <stdint.h>\nuint32_t kernel_get_fw_version(void);',
            }
            for name, text in headers.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text+'\n')
            (root/'harness.c').write_text(HARNESS)
            exe = root/'probe'
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(root), str(ROOT/'scripts/compatibility.c'),
                            str(root/'harness.c'), '-o', str(exe)], check=True)
            for offset in (16, 20, 86):
                with self.subTest(offset=offset):
                    result = subprocess.run([str(exe)], env={'TITLE_OFFSET': str(offset)},
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn('firmware_raw=0x12700000 sdk_initialized=yes', result.stdout)
                    self.assertIn(f'title_offset={offset} buffer_bytes=96', result.stdout)
                    self.assertIn('eboot_candidates=2 title_matches=1 query_failures=0', result.stdout)
                    self.assertIn('permissions and UI compatibility remain untested', result.stdout)
                    self.assertNotIn('PRIVATE99', result.stdout)
            for failure in ('MISSING', 'DUPLICATE', 'QUERY_FAIL', 'BAD_RECORD',
                            'DOUBLE_TITLE', 'TARGET_QUERY_FAIL', 'UNTERMINATED'):
                with self.subTest(failure=failure):
                    result = subprocess.run([str(exe)], env={'TITLE_OFFSET': '16', failure: '1'},
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertNotIn('identification observed', result.stdout)

            # Exercise the same process identities through the actual one-shot
            # permission helper. Synthetic credentials must pass its readback.
            (root/'ps5/kernel.h').write_text(headers['ps5/kernel.h']+'''
uint64_t kernel_get_ucred_authid(pid_t);
int32_t kernel_get_ucred_caps(pid_t, uint8_t[16]);
int32_t kernel_set_ucred_authid(pid_t, uint64_t);
int32_t kernel_set_ucred_caps(pid_t, const uint8_t[16]);
''')
            credentials = r'''
static uint64_t auth=1;
static uint8_t caps[16];
uint64_t kernel_get_ucred_authid(pid_t pid) { if(pid!=41) abort(); return auth; }
int32_t kernel_get_ucred_caps(pid_t pid,uint8_t out[16]) {
    if(pid!=41) abort();
    memcpy(out,caps,16); return 0;
}
int32_t kernel_set_ucred_authid(pid_t pid,uint64_t value) {
    if(pid!=41) abort();
    auth=value; return 0;
}
int32_t kernel_set_ucred_caps(pid_t pid,const uint8_t in[16]) {
    if(pid!=41) abort();
    memcpy(caps,in,16); return 0;
}
#include <signal.h>
int kill(pid_t pid, int signal) {
    if(pid!=41) abort();
    if(signal==SIGTERM) return 0;
    if(signal!=0) abort();
    errno=ESRCH; return -1;
}
'''
            (root/'harness.c').write_text(HARNESS.replace(
                'return 0x12700000;', 'return (uint32_t)strtoul(getenv("FIRMWARE"),NULL,16);')+credentials)
            # These programs start after SDK initialization. The real SDK, not
            # this synthetic harness, rejects unsupported firmware before main.
            for mode in ('promote', 'experiment', 'close'):
                experimental = mode == 'experiment'
                helper = root/mode
                subprocess.run([compiler, '-std=c11', '-D_DEFAULT_SOURCE', '-O1',
                                '-Wall', '-Wextra', '-Werror',
                                '-DNUVIO_PROMOTE_DELAY_MS=0',
                                *(['-DNUVIO_TEST_FW_1270'] if experimental else []),
                                '-I', str(root), str(ROOT/'scripts'/('close.c' if mode == 'close' else 'promote.c')),
                                str(root/'harness.c'), '-o', str(helper)], check=True)
                for firmware in ('3000001', '4030001', '9600001', '12600001', '12700001', '13600001'):
                    for offset in (16, 20, 86):
                        for failure in ('', 'MISSING', 'DUPLICATE', 'DOUBLE_TITLE',
                                        'TARGET_QUERY_FAIL', 'UNTERMINATED', 'BAD_RECORD', 'IDENTITY_CHANGED'):
                            with self.subTest(mode=mode, firmware=firmware, offset=offset, failure=failure):
                                env = {'FIRMWARE': firmware, 'TITLE_OFFSET': str(offset)}
                                if failure:
                                    env[failure] = '1'
                                result = subprocess.run([str(helper)], env=env,
                                                        capture_output=True, text=True, timeout=5)
                                allowed = (not experimental or firmware == '12700001') and not failure
                                no_target = mode == 'close' and failure in (
                                    'MISSING', 'DOUBLE_TITLE', 'TARGET_QUERY_FAIL', 'UNTERMINATED')
                                self.assertEqual(result.returncode, 0 if allowed or no_target else 1, result.stdout)
                                success = ('process exited' if mode == 'close' else 'native network privileges applied')
                                self.assertEqual(success in result.stdout, allowed)

    def test_verify_only_hashes_without_creating_a_backup(self):
        compiler = shutil.which('clang') or shutil.which('cc')
        if not compiler:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = b'old signed container\x00\xff'
            stage = bytes(range(256))*131
            (root/'eboot.bin').write_bytes(installed)
            source = (ROOT/'vendor/control.c').read_text().replace('AURORA', 'NUVIO')
            source = source.replace('../../payloads/common/sha256.h', str(ROOT/'vendor/sha256.h'))
            source = source.replace('/data/homebrew/PPSA99997', str(root))
            source = source.replace('/data/homebrew/ps5-homebrew-dev', str(root/'no-backup'))
            (root/'control.c').write_text(source)
            exe = root/'verify'
            subprocess.run([compiler, '-std=c11', '-D_DEFAULT_SOURCE', '-O1',
                            '-DNUVIO_CONTROL_ACTION=5', '-DNUVIO_VERIFY_ONLY',
                            '-Wall', '-Wextra', '-Werror', str(root/'control.c'),
                            str(ROOT/'vendor/sha256.c'), '-o', str(exe)], check=True)
            for staged in (False, True):
                with self.subTest(staged=staged):
                    if staged:
                        (root/'eboot.bin.nuvio-update').write_bytes(stage)
                    output = subprocess.check_output([str(exe)], text=True, timeout=5)
                    self.assertIn(f'installed bytes={len(installed)} sha256={hashlib.sha256(installed).hexdigest()}', output)
                    expected = (f'stage bytes={len(stage)} sha256={hashlib.sha256(stage).hexdigest()}'
                                if staged else 'stage=absent')
                    self.assertIn(expected, output)
                    self.assertNotIn('backup', output)
                    self.assertFalse((root/'no-backup').exists())
                    self.assertEqual((root/'eboot.bin').read_bytes(), installed)
            # Normal updater builds must still preserve the installed eboot.
            (root/'no-backup').mkdir()
            subprocess.run([compiler, '-std=c11', '-D_DEFAULT_SOURCE', '-O1',
                            '-DNUVIO_CONTROL_ACTION=5', str(root/'control.c'),
                            str(ROOT/'vendor/sha256.c'), '-o', str(exe)], check=True)
            output = subprocess.check_output([str(exe)], text=True, timeout=5)
            self.assertIn(f'backup bytes={len(installed)} sha256={hashlib.sha256(installed).hexdigest()}', output)
            backup = root/'no-backup'/f'nuvio-eboot-backup-{hashlib.sha256(installed).hexdigest()}.bin'
            self.assertEqual(backup.read_bytes(), installed)
