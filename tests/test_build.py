"""FFmpeg cache identities follow compilation inputs, not unrelated edits."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build


class FFmpegCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = json.loads((build.ROOT / 'deps.lock').read_text())
        self.write_manifest()
        self.root_patch = patch.object(build, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write_manifest(self):
        (self.root / 'deps.lock').write_text(json.dumps(self.manifest))

    def test_identity_needs_only_manifest_and_compiler_version(self):
        with patch.object(build, 'fetch', side_effect=AssertionError('download')), \
             patch.object(build.subprocess, 'check_output', side_effect=AssertionError('compiler')):
            identity = build.ffmpeg_cache_id('19.1.7')
            self.assertRegex(identity, r'^[0-9a-f]{16}$')
            self.assertEqual(identity, build.ffmpeg_cache_id('19.1.7'))

    def test_compiler_flags_and_compilation_pins_invalidate_identity(self):
        identity = build.ffmpeg_cache_id('19.1.7')
        self.assertNotEqual(identity, build.ffmpeg_cache_id('20.1.0'))
        with patch.object(build, 'FFMPEG_FLAGS', (*build.FFMPEG_FLAGS, '--disable-network')):
            self.assertNotEqual(identity, build.ffmpeg_cache_id('19.1.7'))
        for key in ('ffmpeg-source', 'ps5-payload-sdk-prebuilt', 'nuvio-pacbrew'):
            with self.subTest(pin=key):
                pin = next(pin for pin in self.manifest['artifacts'] if pin['id'] == key)
                original = pin['sha256']
                pin['sha256'] = '0' * 64
                self.write_manifest()
                self.assertNotEqual(identity, build.ffmpeg_cache_id('19.1.7'))
                pin['sha256'] = original
                self.write_manifest()

    def test_frontend_pins_and_build_script_edits_do_not_invalidate_identity(self):
        identity = build.ffmpeg_cache_id('19.1.7')
        for key in ('nuvio-tv-source', 'nuvio-official-tv-config'):
            with self.subTest(pin=key):
                pin = next(pin for pin in self.manifest['artifacts'] if pin['id'] == key)
                pin['sha256'] = '0' * 64
                self.write_manifest()
                self.assertEqual(identity, build.ffmpeg_cache_id('19.1.7'))
        script = self.root / 'scripts/build.py'
        script.parent.mkdir()
        script.write_text('# unrelated build-script edit\n')
        self.assertEqual(identity, build.ffmpeg_cache_id('19.1.7'))

    def test_matching_cached_install_is_copied_without_extracting_or_compiling(self):
        cache = self.root / 'cache'
        cache.mkdir()
        pin = next(pin for pin in self.manifest['artifacts'] if pin['id'] == 'ffmpeg-source')
        archive = cache / pin['cache_file']
        archive.write_bytes(b'synthetic source archive: never extracted on a cache hit')
        pin['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.write_manifest()
        identity = build.ffmpeg_cache_id('19.1.7')
        cached = cache / ('ffmpeg-' + identity)
        library = cached / 'homebrew/lib/libavcodec.a'
        library.parent.mkdir(parents=True)
        library.write_bytes(b'synthetic cached library')
        (cached / 'stamp.json').write_text(json.dumps({
            'source_sha256': pin['sha256'], 'config_id': identity, 'directory': pin['directory']}))
        sdk = self.root / 'sdk'
        with patch.object(build, 'CACHE', cache), \
             patch.object(build, 'WORK', self.root / 'unused-work'), \
             patch.object(build.subprocess, 'check_output', return_value='19.1.7\n'), \
             patch.object(build.subprocess, 'run', side_effect=AssertionError('compile')), \
             patch.object(build.tarfile, 'open', side_effect=AssertionError('extract')), \
             patch.object(build.urllib.request, 'urlopen', side_effect=AssertionError('download')):
            build.install_ffmpeg(sdk, {'LLVM_CONFIG': '/synthetic/llvm-config'})
        self.assertEqual((sdk / 'target/user/homebrew/lib/libavcodec.a').read_bytes(), library.read_bytes())
        self.assertFalse((self.root / 'unused-work').exists())
