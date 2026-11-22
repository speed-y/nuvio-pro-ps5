#!/usr/bin/env python3
"""Build the pinned Nuvio UI and an EVO-derived PS5 native title on Linux or macOS.

Host only. Generated upstream sources, modules and binaries remain outside Git.
"""
from pathlib import Path
import argparse
import base64
import re
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
import polish
import patches

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get('NUVIO_CACHE_DIR', str(ROOT/'.cache')))
WORK = Path(os.environ.get('NUVIO_WORK_DIR', str(ROOT/'build')))
TITLE = 'PPSA99996'  # Repository-assigned app identity, not a firmware constant.


def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def sdk_install_auth_profile(makefile):
    """Read the public SDK install_app sample's exact signing metadata."""
    joined = makefile.replace('\\\n', ' ')
    authority = re.findall(r'^AUTHID\s*:=\s*(0x[0-9A-Fa-f]+)\s*$', joined, re.MULTILINE)
    info = re.findall(r'^AUTHINFO\s*:=\s*([0-9A-Fa-f \t]+)$', joined, re.MULTILINE)
    if len(authority) != 1 or len(info) != 1:
        raise RuntimeError('Pinned SDK signing profile declarations changed')
    values = info[0].split()
    if len(values) != 0x88 or any(not re.fullmatch('[0-9A-Fa-f]{2}', value) for value in values):
        raise RuntimeError('SDK authentication info must contain exactly 136 bytes')
    if not 0 <= int(authority[0], 16) <= 0xffffffffffffffff:
        raise RuntimeError('SDK authority exceeds its 64-bit field')
    return {'authority': authority[0], 'auth_info': ''.join(values).lower()}


def fetch(key):
    pin = next(p for p in json.loads((ROOT/'deps.lock').read_text())['artifacts'] if p['id'] == key)
    p = CACHE / pin.get('cache_file', key+'.zip')
    if not p.exists():
        tmp = p.with_suffix('.download')
        try:
            with urllib.request.urlopen(pin['url'], timeout=60) as r, tmp.open('wb') as f:
                shutil.copyfileobj(r, f)
            if digest(tmp) != pin['sha256']:
                raise RuntimeError('Downloaded checksum mismatch: '+key)
            tmp.replace(p)
        finally:
            tmp.unlink(missing_ok=True)
    if digest(p) != pin['sha256']:
        raise RuntimeError('Cached checksum mismatch: '+key)
    return pin, p


def source(key):
    pin, archive = fetch(key)
    dest = WORK / pin['directory']
    if dest.exists():
        shutil.rmtree(dest)
    with tarfile.open(archive) as t:
        t.extractall(WORK, filter='data')
    return dest


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError('Pinned source anchor changed: '+str(path))
    path.write_text(text.replace(old, new))


# EVO v0.12.0 includes a Dolby Vision component that mirrors FFmpeg 7.1.1 and
# refuses any other libavcodec, while the pinned pacbrew prefix carries the
# 7.0-era 61.3 headers. Build FFmpeg 7.1.1 with EVO's 'minimal' configuration
# (minus --enable-libdav1d: this port ships no dav1d, so AV1 remains
# unsupported) and install it over the sysroot copy, replacing the pacbrew
# libav* libraries - the same step EVO's own build performs. The result is
# cached in .cache/ so ordinary rebuilds skip the compile.
FFMPEG_FLAGS = (
    # EVO scripts/build-ffmpeg.sh, profile 'minimal', libdav1d removed.
    '--enable-cross-compile',
    '--cross-prefix={sdk}/bin/prospero-',
    '--enable-static',
    '--disable-shared',
    '--arch=x86_64',
    '--target-os=freebsd',
    '--cc=prospero-clang',
    '--cxx=prospero-clang++',
    '--nm=prospero-nm',
    '--strip=prospero-strip',
    '--ar=prospero-ar',
    '--ranlib=prospero-ranlib',
    '--pkg-config=prospero-pkg-config',
    '--disable-debug',
    '--disable-doc',
    '--disable-everything',
    '--disable-programs',
    '--disable-avdevice',
    '--disable-postproc',
    '--disable-encoders',
    '--disable-muxers',
    '--disable-bsfs',
    '--disable-devices',
    '--disable-filters',
    '--enable-network',
    '--enable-openssl',
    '--disable-iconv',
    '--disable-xlib',
    '--disable-sdl2',
    '--enable-swresample',
    '--enable-swscale',
    '--enable-decoder=aac',
    '--enable-decoder=aac_latm',
    '--enable-decoder=ac3',
    '--enable-decoder=eac3',
    '--enable-decoder=dca',
    '--enable-decoder=truehd',
    '--enable-decoder=mlp',
    '--enable-decoder=mp3',
    '--enable-decoder=mp2',
    '--enable-decoder=flac',
    '--enable-decoder=opus',
    '--enable-decoder=vorbis',
    '--enable-decoder=alac',
    '--enable-decoder=pcm_s16le',
    '--enable-decoder=pcm_s16be',
    '--enable-decoder=pcm_s24le',
    '--enable-decoder=pcm_f32le',
    '--enable-decoder=aac_fixed',
    '--enable-decoder=ac3_fixed',
    '--enable-decoder=acelp_kelvin',
    '--enable-decoder=als',
    '--enable-decoder=amrnb',
    '--enable-decoder=amrwb',
    '--enable-decoder=apac',
    '--enable-decoder=ape',
    '--enable-decoder=aptx',
    '--enable-decoder=aptx_hd',
    '--enable-decoder=atrac1',
    '--enable-decoder=atrac3',
    '--enable-decoder=atrac3al',
    '--enable-decoder=atrac3p',
    '--enable-decoder=atrac3pal',
    '--enable-decoder=atrac9',
    '--enable-decoder=binkaudio_dct',
    '--enable-decoder=binkaudio_rdft',
    '--enable-decoder=bmv_audio',
    '--enable-decoder=bonk',
    '--enable-decoder=cook',
    '--enable-decoder=dfpwm',
    '--enable-decoder=dolby_e',
    '--enable-decoder=dsd_lsbf',
    '--enable-decoder=dsd_lsbf_planar',
    '--enable-decoder=dsd_msbf',
    '--enable-decoder=dsd_msbf_planar',
    '--enable-decoder=dsicinaudio',
    '--enable-decoder=dss_sp',
    '--enable-decoder=dst',
    '--enable-decoder=evrc',
    '--enable-decoder=fastaudio',
    '--enable-decoder=ffwavesynth',
    '--enable-decoder=ftr',
    '--enable-decoder=g723_1',
    '--enable-decoder=g729',
    '--enable-decoder=gsm',
    '--enable-decoder=gsm_ms',
    '--enable-decoder=hca',
    '--enable-decoder=hcom',
    '--enable-decoder=iac',
    '--enable-decoder=ilbc',
    '--enable-decoder=imc',
    '--enable-decoder=interplay_acm',
    '--enable-decoder=mace3',
    '--enable-decoder=mace6',
    '--enable-decoder=metasound',
    '--enable-decoder=misc4',
    '--enable-decoder=mp1',
    '--enable-decoder=mp1float',
    '--enable-decoder=mp2float',
    '--enable-decoder=mp3adu',
    '--enable-decoder=mp3adufloat',
    '--enable-decoder=mp3float',
    '--enable-decoder=mp3on4',
    '--enable-decoder=mp3on4float',
    '--enable-decoder=mpc7',
    '--enable-decoder=mpc8',
    '--enable-decoder=msnsiren',
    '--enable-decoder=nellymoser',
    '--enable-decoder=on2avc',
    '--enable-decoder=osq',
    '--enable-decoder=paf_audio',
    '--enable-decoder=qcelp',
    '--enable-decoder=qdm2',
    '--enable-decoder=qdmc',
    '--enable-decoder=qoa',
    '--enable-decoder=ra_144',
    '--enable-decoder=ra_288',
    '--enable-decoder=ralf',
    '--enable-decoder=sbc',
    '--enable-decoder=shorten',
    '--enable-decoder=sipr',
    '--enable-decoder=siren',
    '--enable-decoder=smackaud',
    '--enable-decoder=sonic',
    '--enable-decoder=tak',
    '--enable-decoder=truespeech',
    '--enable-decoder=tta',
    '--enable-decoder=twinvq',
    '--enable-decoder=vmdaudio',
    '--enable-decoder=wavarc',
    '--enable-decoder=wavpack',
    '--enable-decoder=wmalossless',
    '--enable-decoder=wmapro',
    '--enable-decoder=wmav1',
    '--enable-decoder=wmav2',
    '--enable-decoder=wmavoice',
    '--enable-decoder=ws_snd1',
    '--enable-decoder=xma1',
    '--enable-decoder=xma2',
    '--enable-decoder=pcm_alaw',
    '--enable-decoder=pcm_bluray',
    '--enable-decoder=pcm_dvd',
    '--enable-decoder=pcm_f16le',
    '--enable-decoder=pcm_f24le',
    '--enable-decoder=pcm_f32be',
    '--enable-decoder=pcm_f64be',
    '--enable-decoder=pcm_f64le',
    '--enable-decoder=pcm_lxf',
    '--enable-decoder=pcm_mulaw',
    '--enable-decoder=pcm_s16be_planar',
    '--enable-decoder=pcm_s16le_planar',
    '--enable-decoder=pcm_s24be',
    '--enable-decoder=pcm_s24daud',
    '--enable-decoder=pcm_s24le_planar',
    '--enable-decoder=pcm_s32be',
    '--enable-decoder=pcm_s32le',
    '--enable-decoder=pcm_s32le_planar',
    '--enable-decoder=pcm_s64be',
    '--enable-decoder=pcm_s64le',
    '--enable-decoder=pcm_s8',
    '--enable-decoder=pcm_s8_planar',
    '--enable-decoder=pcm_sga',
    '--enable-decoder=pcm_u16be',
    '--enable-decoder=pcm_u16le',
    '--enable-decoder=pcm_u24be',
    '--enable-decoder=pcm_u24le',
    '--enable-decoder=pcm_u32be',
    '--enable-decoder=pcm_u32le',
    '--enable-decoder=pcm_u8',
    '--enable-decoder=pcm_vidc',
    '--enable-decoder=adpcm_4xm',
    '--enable-decoder=adpcm_adx',
    '--enable-decoder=adpcm_afc',
    '--enable-decoder=adpcm_agm',
    '--enable-decoder=adpcm_aica',
    '--enable-decoder=adpcm_argo',
    '--enable-decoder=adpcm_ct',
    '--enable-decoder=adpcm_dtk',
    '--enable-decoder=adpcm_ea',
    '--enable-decoder=adpcm_ea_maxis_xa',
    '--enable-decoder=adpcm_ea_r1',
    '--enable-decoder=adpcm_ea_r2',
    '--enable-decoder=adpcm_ea_r3',
    '--enable-decoder=adpcm_ea_xas',
    '--enable-decoder=adpcm_g722',
    '--enable-decoder=adpcm_g726',
    '--enable-decoder=adpcm_g726le',
    '--enable-decoder=adpcm_ima_acorn',
    '--enable-decoder=adpcm_ima_alp',
    '--enable-decoder=adpcm_ima_amv',
    '--enable-decoder=adpcm_ima_apc',
    '--enable-decoder=adpcm_ima_apm',
    '--enable-decoder=adpcm_ima_cunning',
    '--enable-decoder=adpcm_ima_dat4',
    '--enable-decoder=adpcm_ima_dk3',
    '--enable-decoder=adpcm_ima_dk4',
    '--enable-decoder=adpcm_ima_ea_eacs',
    '--enable-decoder=adpcm_ima_ea_sead',
    '--enable-decoder=adpcm_ima_iss',
    '--enable-decoder=adpcm_ima_moflex',
    '--enable-decoder=adpcm_ima_mtf',
    '--enable-decoder=adpcm_ima_oki',
    '--enable-decoder=adpcm_ima_qt',
    '--enable-decoder=adpcm_ima_rad',
    '--enable-decoder=adpcm_ima_smjpeg',
    '--enable-decoder=adpcm_ima_ssi',
    '--enable-decoder=adpcm_ima_wav',
    '--enable-decoder=adpcm_ima_ws',
    '--enable-decoder=adpcm_ms',
    '--enable-decoder=adpcm_mtaf',
    '--enable-decoder=adpcm_psx',
    '--enable-decoder=adpcm_sbpro_2',
    '--enable-decoder=adpcm_sbpro_3',
    '--enable-decoder=adpcm_sbpro_4',
    '--enable-decoder=adpcm_swf',
    '--enable-decoder=adpcm_thp',
    '--enable-decoder=adpcm_thp_le',
    '--enable-decoder=adpcm_vima',
    '--enable-decoder=adpcm_xa',
    '--enable-decoder=adpcm_xmd',
    '--enable-decoder=adpcm_yamaha',
    '--enable-decoder=adpcm_zork',
    '--enable-decoder=cbd2_dpcm',
    '--enable-decoder=derf_dpcm',
    '--enable-decoder=gremlin_dpcm',
    '--enable-decoder=interplay_dpcm',
    '--enable-decoder=roq_dpcm',
    '--enable-decoder=sdx2_dpcm',
    '--enable-decoder=sol_dpcm',
    '--enable-decoder=wady_dpcm',
    '--enable-decoder=xan_dpcm',
    '--enable-decoder=vc1',
    '--enable-decoder=wmv1',
    '--enable-decoder=wmv2',
    '--enable-decoder=wmv3',
    '--enable-decoder=msmpeg4v1',
    '--enable-decoder=msmpeg4v2',
    '--enable-decoder=msmpeg4v3',
    '--enable-decoder=mpeg1video',
    '--enable-decoder=flv',
    '--enable-decoder=vp6',
    '--enable-decoder=vp6a',
    '--enable-decoder=vp6f',
    '--enable-decoder=h263',
    '--enable-decoder=h263i',
    '--enable-decoder=h263p',
    '--enable-decoder=msvideo1',
    '--enable-decoder=cinepak',
    '--enable-decoder=indeo3',
    '--enable-decoder=indeo4',
    '--enable-decoder=indeo5',
    '--enable-decoder=huffyuv',
    '--enable-decoder=ffv1',
    '--enable-decoder=utvideo',
    '--enable-decoder=qtrle',
    '--enable-decoder=rpza',
    '--enable-decoder=smc',
    '--enable-decoder=svq1',
    '--enable-decoder=svq3',
    '--enable-decoder=mjpegb',
    '--enable-decoder=theora',
    '--enable-decoder=prores',
    '--enable-decoder=dnxhd',
    '--enable-decoder=dvvideo',
    '--enable-decoder=cavs',
    '--enable-decoder=rv10',
    '--enable-decoder=rv20',
    '--enable-decoder=rv30',
    '--enable-decoder=rv40',
    '--enable-decoder=webp',
    '--enable-decoder=webvtt',
    '--enable-decoder=text',
    '--enable-decoder=microdvd',
    '--enable-decoder=sami',
    '--enable-decoder=subviewer',
    '--enable-decoder=subviewer1',
    '--enable-decoder=mpl2',
    '--enable-decoder=vplayer',
    '--enable-decoder=pjs',
    '--enable-decoder=jacosub',
    '--enable-decoder=realtext',
    '--enable-decoder=stl',
    '--enable-decoder=xsub',
    '--enable-decoder=ccaption',
    '--enable-decoder=h264',
    '--enable-decoder=hevc',
    '--enable-decoder=vp9',
    '--enable-decoder=vp8',
    '--enable-decoder=mpeg2video',
    '--enable-decoder=mpeg4',
    '--enable-decoder=subrip',
    '--enable-decoder=ass',
    '--enable-decoder=srt',
    '--enable-decoder=movtext',
    '--enable-decoder=pgssub',
    '--enable-decoder=dvdsub',
    '--enable-decoder=dvbsub',
    '--enable-decoder=mjpeg',
    '--enable-decoder=png',
    '--enable-demuxer=matroska',
    '--enable-demuxer=mov',
    '--enable-demuxer=mpegts',
    '--enable-demuxer=mpegps',
    '--enable-demuxer=avi',
    '--enable-demuxer=flac',
    '--enable-demuxer=mp3',
    '--enable-demuxer=ogg',
    '--enable-demuxer=wav',
    '--enable-demuxer=aac',
    '--enable-demuxer=ac3',
    '--enable-demuxer=eac3',
    '--enable-demuxer=dts',
    '--enable-demuxer=truehd',
    '--enable-demuxer=h264',
    '--enable-demuxer=hevc',
    '--enable-demuxer=srt',
    '--enable-demuxer=ass',
    '--enable-demuxer=image2',
    '--enable-demuxer=ivf',
    '--enable-demuxer=obu',
    '--enable-demuxer=av1',
    '--enable-bsf=av1_frame_merge',
    '--enable-demuxer=hls',
    '--enable-demuxer=dash',
    '--enable-libxml2',
    '--enable-demuxer=adx',
    '--enable-demuxer=aiff',
    '--enable-demuxer=amr',
    '--enable-demuxer=amrnb',
    '--enable-demuxer=amrwb',
    '--enable-demuxer=apac',
    '--enable-demuxer=ape',
    '--enable-demuxer=aptx',
    '--enable-demuxer=aptx_hd',
    '--enable-demuxer=argo_asf',
    '--enable-demuxer=asf',
    '--enable-demuxer=ast',
    '--enable-demuxer=au',
    '--enable-demuxer=bfstm',
    '--enable-demuxer=bonk',
    '--enable-demuxer=brstm',
    '--enable-demuxer=caf',
    '--enable-demuxer=codec2',
    '--enable-demuxer=dfpwm',
    '--enable-demuxer=dsf',
    '--enable-demuxer=dtshd',
    '--enable-demuxer=g723_1',
    '--enable-demuxer=g729',
    '--enable-demuxer=gsm',
    '--enable-demuxer=hca',
    '--enable-demuxer=hcom',
    '--enable-demuxer=iff',
    '--enable-demuxer=ilbc',
    '--enable-demuxer=ircam',
    '--enable-demuxer=mlp',
    '--enable-demuxer=mpc',
    '--enable-demuxer=mpc8',
    '--enable-demuxer=nistsphere',
    '--enable-demuxer=oma',
    '--enable-demuxer=osq',
    '--enable-demuxer=pcm_alaw',
    '--enable-demuxer=pcm_f32be',
    '--enable-demuxer=pcm_f32le',
    '--enable-demuxer=pcm_f64be',
    '--enable-demuxer=pcm_f64le',
    '--enable-demuxer=pcm_mulaw',
    '--enable-demuxer=pcm_s16be',
    '--enable-demuxer=pcm_s16le',
    '--enable-demuxer=pcm_s24be',
    '--enable-demuxer=pcm_s24le',
    '--enable-demuxer=pcm_s32be',
    '--enable-demuxer=pcm_s32le',
    '--enable-demuxer=pcm_s8',
    '--enable-demuxer=pcm_u16be',
    '--enable-demuxer=pcm_u16le',
    '--enable-demuxer=pcm_u24be',
    '--enable-demuxer=pcm_u24le',
    '--enable-demuxer=pcm_u32be',
    '--enable-demuxer=pcm_u32le',
    '--enable-demuxer=pcm_u8',
    '--enable-demuxer=pcm_vidc',
    '--enable-demuxer=pvf',
    '--enable-demuxer=qoa',
    '--enable-demuxer=rso',
    '--enable-demuxer=rm',
    '--enable-demuxer=sbc',
    '--enable-demuxer=shorten',
    '--enable-demuxer=sln',
    '--enable-demuxer=sox',
    '--enable-demuxer=spdif',
    '--enable-demuxer=tak',
    '--enable-demuxer=tta',
    '--enable-demuxer=voc',
    '--enable-demuxer=vqf',
    '--enable-demuxer=w64',
    '--enable-demuxer=wavarc',
    '--enable-demuxer=wv',
    '--enable-demuxer=wve',
    '--enable-demuxer=xa',
    '--enable-demuxer=xwma',
    '--enable-demuxer=asf',
    '--enable-demuxer=asf_o',
    '--enable-demuxer=flv',
    '--enable-demuxer=live_flv',
    '--enable-demuxer=rm',
    '--enable-demuxer=dv',
    '--enable-demuxer=mxf',
    '--enable-demuxer=webvtt',
    '--enable-demuxer=microdvd',
    '--enable-demuxer=sami',
    '--enable-demuxer=subviewer',
    '--enable-demuxer=subviewer1',
    '--enable-demuxer=mpl2',
    '--enable-demuxer=vplayer',
    '--enable-demuxer=pjs',
    '--enable-demuxer=jacosub',
    '--enable-demuxer=realtext',
    '--enable-demuxer=stl',
    '--enable-demuxer=vc1',
    '--enable-demuxer=vc1t',
    '--enable-demuxer=m4v',
    '--enable-demuxer=ivf',
    '--enable-demuxer=mpegvideo',
    '--enable-parser=h264',
    '--enable-parser=hevc',
    '--enable-parser=vp9',
    '--enable-parser=av1',
    '--enable-parser=aac',
    '--enable-parser=aac_latm',
    '--enable-parser=ac3',
    '--enable-parser=dca',
    '--enable-parser=mlp',
    '--enable-parser=flac',
    '--enable-parser=opus',
    '--enable-parser=vorbis',
    '--enable-parser=mpegaudio',
    '--enable-parser=mpegvideo',
    '--enable-parser=mpeg4video',
    '--enable-parser=adx',
    '--enable-parser=amr',
    '--enable-parser=cook',
    '--enable-parser=dolby_e',
    '--enable-parser=dvaudio',
    '--enable-parser=ftr',
    '--enable-parser=g723_1',
    '--enable-parser=g729',
    '--enable-parser=gsm',
    '--enable-parser=misc4',
    '--enable-parser=sbc',
    '--enable-parser=sipr',
    '--enable-parser=tak',
    '--enable-parser=xma',
    '--enable-parser=vc1',
    '--enable-parser=h263',
    '--enable-parser=webp',
    '--enable-bsf=h264_mp4toannexb',
    '--enable-bsf=hevc_mp4toannexb',
    '--enable-bsf=extract_extradata',
    '--enable-bsf=aac_adtstoasc',
    '--enable-bsf=vp9_superframe',
    '--enable-filter=aformat',
    '--enable-filter=aresample',
    '--enable-filter=anull',
    '--enable-filter=format',
    '--enable-filter=scale',
    '--enable-filter=null',
    '--enable-protocol=file',
    '--enable-protocol=pipe',
    '--enable-protocol=http',
    '--enable-protocol=https',
    '--enable-protocol=tcp',
    '--enable-protocol=tls',
    '--enable-protocol=ftp',
    '--enable-protocol=crypto',
)


def ffmpeg_cache_id(compiler):
    """Identify compilation inputs using the llvm-config version, without fetching."""
    pins = {pin['id']: pin for pin in json.loads((ROOT/'deps.lock').read_text())['artifacts']}
    sources = [pins[key]['sha256'] for key in (
        'ffmpeg-source', 'ps5-payload-sdk-prebuilt', 'nuvio-pacbrew')]
    return hashlib.sha256('\n'.join([*sources, compiler, *FFMPEG_FLAGS]).encode()).hexdigest()[:16]


def install_ffmpeg(sdk, env):
    """Build the pinned FFmpeg over the sysroot homebrew prefix (cached)."""
    pin, archive = fetch('ffmpeg-source')
    compiler = subprocess.check_output([env['LLVM_CONFIG'], '--version'], text=True).strip()
    config_id = ffmpeg_cache_id(compiler)
    cached = CACHE / ('ffmpeg-' + config_id)
    stamp = {'source_sha256': pin['sha256'], 'config_id': config_id, 'directory': pin['directory']}
    stamp_file = cached / 'stamp.json'
    if stamp_file.is_file() and json.loads(stamp_file.read_text()) == stamp:
        shutil.copytree(cached / 'homebrew', sdk / 'target/user/homebrew', dirs_exist_ok=True)
        print('FFmpeg', pin['directory'], 'installed from cache')
        return
    src = WORK / pin['directory']
    if src.exists():
        shutil.rmtree(src)
    with tarfile.open(archive) as t:
        t.extractall(WORK, filter='data')
    stage = WORK / 'ffmpeg-stage'
    if stage.exists():
        shutil.rmtree(stage)

    def logged(args, name, **kwargs):
        log = WORK / ('ffmpeg-' + name + '.log')
        with log.open('w') as f:
            proc = subprocess.run([str(a) for a in args], stdout=f, stderr=subprocess.STDOUT, **kwargs)
        if proc.returncode != 0:
            raise RuntimeError('FFmpeg ' + name + ' failed; tail of ' + str(log) + ':\n' + log.read_text()[-2000:])

    print('Building FFmpeg', pin['directory'], '(first build is slow; cached afterwards)')
    flags = [flag.format(sdk=sdk) for flag in FFMPEG_FLAGS]
    logged([src / 'configure', '--prefix=/user/homebrew', *flags], 'configure', cwd=src, env=env)
    logged(['make', '-j' + str(os.cpu_count() or 4)], 'build', cwd=src, env=env)
    logged(['make', 'install', 'DESTDIR=' + str(stage)], 'install', cwd=src, env=env)
    for lib in ('libavcodec.a', 'libavformat.a', 'libavutil.a', 'libswresample.a', 'libswscale.a'):
        if not (stage / 'user/homebrew/lib' / lib).is_file():
            raise RuntimeError('FFmpeg did not produce ' + lib)
    tmp = cached.with_name(cached.name + '.staging')
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(stage / 'user/homebrew', tmp / 'homebrew')
    (tmp / 'stamp.json').write_text(json.dumps(stamp, indent=2) + '\n')
    if cached.exists():
        shutil.rmtree(cached)
    tmp.rename(cached)
    shutil.copytree(cached / 'homebrew', sdk / 'target/user/homebrew', dirs_exist_ok=True)
    print('FFmpeg', pin['directory'], 'built and installed over the sysroot')


# Extra faces for the HUD subtitle atlas. The pinned kit already carries
# Noto Sans, Arabic, Hebrew and both symbol faces. Thai and Devanagari do not.
# The googlefonts/noto-fonts URLs redirect to notofonts/noto-fonts.
FALLBACK_EXTRA_FONTS = (
    {'id': 'noto-sans-thai-regular', 'file': 'NotoSansThai-Regular.ttf'},
    {'id': 'noto-sans-devanagari-regular', 'file': 'NotoSansDevanagari-Regular.ttf'},
)
FALLBACK_BAKE_FONTS = (
    'NotoSans-Regular.ttf',
    'NotoSansThai-Regular.ttf',
    'NotoSansDevanagari-Regular.ttf',
    'NotoSansArabic-Regular.ttf',
    'NotoSansHebrew-Regular.ttf',
    'NotoSansSymbols-Regular.ttf',
    'NotoSansSymbols2-Regular.ttf',
)
FALLBACK_RANGE_ANCHOR = '    {0x1E00, 0x1EFF},   // Latin Extended Additional (Vietnamese)\n'
FALLBACK_RANGE_ADDITION = '    {0x0E00, 0x0E7F},   // Thai\n    {0x0900, 0x097F},   // Devanagari\n'
FALLBACK_COMMENT_OLD = '// Latin (with accents and Vietnamese), Greek, Cyrillic, Hebrew, Arabic with\n'
FALLBACK_COMMENT_NEW = '// Latin (with accents and Vietnamese), Greek, Cyrillic, Thai, Devanagari, Hebrew, Arabic with\n'


def host_cxx():
    """Return clang++ or g++, whichever can compile a C++17 program."""
    for name in ('clang++', 'g++'):
        compiler = shutil.which(name)
        if not compiler:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'probe.cpp'
            out = Path(tmp) / 'probe'
            src.write_text('int main(){return 0;}\n')
            proc = subprocess.run([compiler, '-std=c++17', str(src), '-o', str(out)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode == 0:
            return compiler
    raise RuntimeError('No host C++ compiler can build the font baker. Install clang++ or g++.')


def patch_fallback_baker(text):
    """Add Thai and Devanagari ranges after Latin Extended Additional.

    A second call leaves an already patched baker unchanged. A missing anchor
    is a hard failure so a moved upstream range cannot bake the old atlas.
    """
    if text.count(FALLBACK_RANGE_ANCHOR) != 1:
        raise RuntimeError('Pinned font baker is missing the Latin Extended Additional range')
    block = FALLBACK_RANGE_ANCHOR + FALLBACK_RANGE_ADDITION
    if block not in text:
        if '0x0E00' in text or '{0x0900, 0x097F}' in text:
            raise RuntimeError('Pinned font baker has Thai or Devanagari ranges outside the expected anchor')
        text = text.replace(FALLBACK_RANGE_ANCHOR, block, 1)
    if FALLBACK_COMMENT_OLD in text:
        if text.count(FALLBACK_COMMENT_OLD) != 1:
            raise RuntimeError('Pinned font baker comment anchor is not unique')
        text = text.replace(FALLBACK_COMMENT_OLD, FALLBACK_COMMENT_NEW, 1)
    return text


def huifont_summary(path):
    """Read a baked SDF font header and the code points it contains."""
    data = path.read_bytes()
    if len(data) < 40:
        raise RuntimeError('Fallback font is too small: ' + str(path))
    magic, version, width, height, pixel_size, sdf_range, _ascent, _descent, _gap, glyphs, kerns = struct.unpack_from(
        '<IIHHfffffII', data)
    if magic != 0x46505a50 or version != 1:
        raise RuntimeError('Fallback font is not a huifont v1: ' + str(path))
    expect = 40 + glyphs * 24 + kerns * 12 + width * height
    if len(data) != expect:
        raise RuntimeError('Fallback font size mismatch: ' + str(path))
    codes = set()
    offset = 40
    for _ in range(glyphs):
        codes.add(struct.unpack_from('<I', data, offset)[0])
        offset += 24
    return codes, {'width': width, 'height': height, 'glyphs': glyphs, 'bytes': len(data),
                   'pixel_size': pixel_size, 'sdf_range': sdf_range}


def fallback_font_file(dest, name):
    """Use the kit face when it exists. Download only the pinned extra faces."""
    bundled = dest / 'third_party/fonts' / name
    if bundled.is_file():
        return bundled
    extra = next((item for item in FALLBACK_EXTRA_FONTS if item['file'] == name), None)
    if extra is None:
        raise RuntimeError('ps5-homebrew-ui is missing third_party/fonts/' + name)
    _pin, cached = fetch(extra['id'])
    return cached


def bake_subtitle_fallback(dest, evo):
    """Rebuild noto-fallback.huifont so the HUD can draw Thai and Devanagari.

    The title embeds projects/evoplayer/assets/hui/fonts/noto-fallback.huifont.
    The kit copy under assets/fonts is the baker output, not the bundled file.
    """
    baker_src = dest / 'tools/font-baker/bake_fallback.cpp'
    if not baker_src.is_file():
        raise RuntimeError('ps5-homebrew-ui is missing tools/font-baker/bake_fallback.cpp')
    baker_src.write_text(patch_fallback_baker(baker_src.read_text()))
    fonts = [fallback_font_file(dest, name) for name in FALLBACK_BAKE_FONTS]
    out = dest / 'assets/fonts/noto-fallback.huifont'
    if not out.parent.is_dir():
        raise RuntimeError('ps5-homebrew-ui is missing assets/fonts')
    bundled = evo / 'projects/evoplayer/assets/hui/fonts/noto-fallback.huifont'
    if not bundled.is_file():
        raise RuntimeError('EVO is missing the embedded HUD fallback font')
    WORK.mkdir(parents=True, exist_ok=True)
    compiler = host_cxx()
    tool = WORK / 'bake_fallback'
    run([compiler, '-O2', '-std=c++17', '-o', tool, baker_src])
    command = [tool, out, '48', '6', '4096', *fonts]
    proc = subprocess.run([str(a) for a in command], capture_output=True, text=True)
    if proc.returncode != 0 and 'too small' in proc.stderr:
        print('Fallback atlas 4096 is too small; retrying at 8192')
        command[4] = '8192'
        proc = subprocess.run([str(a) for a in command], capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or 'font baker failed').strip()
        raise RuntimeError('Fallback font bake failed:\n' + detail[-2000:])
    if proc.stdout.strip():
        print(proc.stdout.strip())
    codes, info = huifont_summary(out)
    for codepoint, label in ((0x0E01, 'Thai'), (0x0915, 'Devanagari'), (0x0627, 'Arabic'), (0x05D0, 'Hebrew')):
        if codepoint not in codes:
            raise RuntimeError('Baked fallback font has no ' + label + ' glyph U+' + format(codepoint, '04X'))
    shutil.copyfile(out, bundled)
    print('Fallback font', info['glyphs'], 'glyphs, atlas',
          str(info['width']) + 'x' + str(info['height']) + ',', info['bytes'], 'bytes')


# Subset OTFs from notofonts/noto-cjk @ 165c01b46ea533872e002e0785ff17e44f6d97d8.
# The HUD shader has six font slots and is already compiled, so these faces are
# rasterized on demand into the existing complex-text atlas. A /data copy wins.
CJK_FONTS = (
    {'id': 'noto-sans-sc-regular', 'file': 'NotoSansSC-Regular.otf'},
    {'id': 'noto-sans-tc-regular', 'file': 'NotoSansTC-Regular.otf'},
    {'id': 'noto-sans-jp-regular', 'file': 'NotoSansJP-Regular.otf'},
    {'id': 'noto-sans-kr-regular', 'file': 'NotoSansKR-Regular.otf'},
)
CJK_COMPLEX_PATCHES = (
    (
        '    f_sc,\n    f_jp,\n    f_kr,\n',
        '    f_sc,\n    f_tc,\n    f_jp,\n    f_kr,\n',
        'CJK face id',
    ),
    (
        '    {nullptr, "NotoSansSC-Regular.otf", "zh"},\n'
        '    {nullptr, "NotoSansJP-Regular.otf", "ja"},\n'
        '    {nullptr, "NotoSansKR-Regular.otf", "ko"},\n',
        '    {"fonts/NotoSansSC-Regular.otf", "NotoSansSC-Regular.otf", "zh"},\n'
        '    {"fonts/NotoSansTC-Regular.otf", "NotoSansTC-Regular.otf", "zh-Hant"},\n'
        '    {"fonts/NotoSansJP-Regular.otf", "NotoSansJP-Regular.otf", "ja"},\n'
        '    {"fonts/NotoSansKR-Regular.otf", "NotoSansKR-Regular.otf", "ko"},\n',
        'CJK face table',
    ),
    (
        '        const int mask = cjk_mask();\n'
        '        if (mask & (1 << (want - f_sc)))\n'
        '            return want;\n'
        '        for (int f = f_sc; f <= f_kr; ++f)\n'
        '            if (mask & (1 << (f - f_sc)))\n'
        '                return f;\n'
        '        return -1;\n',
        '        const int mask = cjk_mask();\n'
        '        auto present = [&](int face) {\n'
        '            if (mask & (1 << (face - f_sc)))\n'
        '                return true;\n'
        '            return kFaces[face].bundle != nullptr;\n'
        '        };\n'
        '        if (present(want))\n'
        '            return want;\n'
        '        for (int f = f_sc; f <= f_kr; ++f)\n'
        '            if (present(f))\n'
        '                return f;\n'
        '        return -1;\n',
        'CJK face choice',
    ),
    (
        '        if (kFaces[id].bundle)\n'
        '        {\n'
        '            const EvoRmlBundleFile *b = evo_rmlui_bundle_find(kFaces[id].bundle);\n'
        '            if (b)\n'
        '            {\n'
        '                f.data = b->data;\n'
        '                size = b->size;\n'
        '            }\n'
        '        }\n'
        '        else\n'
        '        {\n'
        '            const std::string path = cjk_path(id);\n'
        '            if (std::FILE *fp = std::fopen(path.c_str(), "rb"))\n'
        '            {\n'
        '                std::fseek(fp, 0, SEEK_END);\n'
        '                const long n = std::ftell(fp);\n'
        '                std::fseek(fp, 0, SEEK_SET);\n'
        '                if (n > 0)\n'
        '                {\n'
        '                    f.owned.resize(static_cast<std::size_t>(n));\n'
        '                    if (std::fread(f.owned.data(), 1, f.owned.size(), fp) == f.owned.size())\n'
        '                    {\n'
        '                        f.data = f.owned.data();\n'
        '                        size = f.owned.size();\n'
        '                    }\n'
        '                }\n'
        '                std::fclose(fp);\n'
        '            }\n'
        '        }\n',
        '        if (kFaces[id].file)\n'
        '        {\n'
        '            const std::string path = cjk_path(id);\n'
        '            if (std::FILE *fp = std::fopen(path.c_str(), "rb"))\n'
        '            {\n'
        '                std::fseek(fp, 0, SEEK_END);\n'
        '                const long n = std::ftell(fp);\n'
        '                std::fseek(fp, 0, SEEK_SET);\n'
        '                if (n > 0)\n'
        '                {\n'
        '                    f.owned.resize(static_cast<std::size_t>(n));\n'
        '                    if (std::fread(f.owned.data(), 1, f.owned.size(), fp) == f.owned.size())\n'
        '                    {\n'
        '                        f.data = f.owned.data();\n'
        '                        size = f.owned.size();\n'
        '                    }\n'
        '                }\n'
        '                std::fclose(fp);\n'
        '            }\n'
        '        }\n'
        '        if ((!f.data || size == 0) && kFaces[id].bundle)\n'
        '        {\n'
        '            const EvoRmlBundleFile *b = evo_rmlui_bundle_find(kFaces[id].bundle);\n'
        '            if (b)\n'
        '            {\n'
        '                f.data = b->data;\n'
        '                size = b->size;\n'
        '            }\n'
        '        }\n',
        'CJK font load',
    ),
    (
        '        Face *f = load(id);\n'
        '        if (!f)\n'
        '            return nullptr;\n'
        '        if (shapes.size() >= kShapeCacheMax)\n',
        '        Face *f = load(id);\n'
        '        if (!f && id < f_sc)\n'
        '            return nullptr;\n'
        '        if (shapes.size() >= kShapeCacheMax)\n',
        'CJK face fallback',
    ),
    (
        'struct ShapedGlyph\n'
        '{\n'
        '    std::uint32_t id;\n'
        '    float advance, dx, dy; /* in ems; y up */\n'
        '};\n',
        'struct ShapedGlyph\n'
        '{\n'
        '    std::uint32_t id;\n'
        '    int face = -1;\n'
        '    float advance, dx, dy; /* in ems; y up */\n'
        '};\n',
        'CJK glyph face',
    ),
    (
        '    /* The face a run of one group is drawn with. */\n',
        '    /* True when some CJK face has this scalar. A miss stays missing\n'
        '     * so the caption can fall back to RmlUi instead of a box. */\n'
        '    bool cjk_glyph(char32_t codepoint)\n'
        '    {\n'
        '        int prefer = f_sc;\n'
        '        if (is_kana(codepoint))\n'
        '            prefer = f_jp;\n'
        '        else if (is_hangul(codepoint))\n'
        '            prefer = f_kr;\n'
        '        const int order[] = {prefer, f_sc, f_tc, f_jp, f_kr};\n'
        '        for (const int candidate : order)\n'
        '        {\n'
        '            if (candidate < f_sc || candidate > f_kr)\n'
        '                continue;\n'
        '            Face *chosen = load(candidate);\n'
        '            if (chosen != nullptr &&\n'
        '                FT_Get_Char_Index(chosen->ft, static_cast<FT_ULong>(codepoint)) != 0)\n'
        '                return true;\n'
        '        }\n'
        '        return false;\n'
        '    }\n'
        '\n'
        '    /* The face a run of one group is drawn with. */\n',
        'CJK coverage probe',
    ),
    (
        '            Shaped &plain = shapes[key];\n'
        '            const float em = static_cast<float>(f->upem);\n'
        '            for (const char32_t c : run)\n'
        '            {\n'
        '                hb_codepoint_t gid = 0;\n'
        '                if (!hb_font_get_nominal_glyph(f->font, c, &gid))\n'
        '                    gid = 0;\n'
        '                ShapedGlyph g;\n'
        '                g.id = gid;\n'
        '                g.advance = static_cast<float>(hb_font_get_glyph_h_advance(f->font, gid)) / em;\n'
        '                g.dx = g.dy = 0.0f;\n'
        '                plain.glyphs.push_back(g);\n'
        '                plain.width += g.advance;\n'
        '            }\n',
        '            Shaped &plain = shapes[key];\n'
        '            const int order[] = {id, f_sc, f_tc, f_jp, f_kr};\n'
        '            for (const char32_t c : run)\n'
        '            {\n'
        '                int use = -1;\n'
        '                hb_codepoint_t gid = 0;\n'
        '                Face *chosen = nullptr;\n'
        '                for (const int candidate : order)\n'
        '                {\n'
        '                    if (candidate < f_sc || candidate > f_kr)\n'
        '                        continue;\n'
        '                    Face *attempt = load(candidate);\n'
        '                    if (attempt && hb_font_get_nominal_glyph(attempt->font, c, &gid))\n'
        '                    {\n'
        '                        use = candidate;\n'
        '                        chosen = attempt;\n'
        '                        break;\n'
        '                    }\n'
        '                }\n'
        '                if (use < 0 || chosen == nullptr)\n'
        '                    continue;\n'
        '                const float em = static_cast<float>(chosen->upem);\n'
        '                ShapedGlyph g;\n'
        '                g.id = gid;\n'
        '                g.face = use;\n'
        '                g.advance = static_cast<float>(hb_font_get_glyph_h_advance(chosen->font, gid)) / em;\n'
        '                g.dx = g.dy = 0.0f;\n'
        '                plain.glyphs.push_back(g);\n'
        '                plain.width += g.advance;\n'
        '            }\n',
        'CJK shaping',
    ),
    (
        '            g.id = info[i].codepoint;\n'
        '            g.advance = static_cast<float>(pos[i].x_advance) / em;\n',
        '            g.id = info[i].codepoint;\n'
        '            g.face = id;\n'
        '            g.advance = static_cast<float>(pos[i].x_advance) / em;\n',
        'shaped glyph face',
    ),
    (
        '                const Cached *c = impl_->glyph(*this, face, sg.id);\n',
        '                const Cached *c = impl_->glyph(*this, sg.face, sg.id);\n',
        'CJK glyph atlas',
    ),
    (
        '    const Group g = group_of(codepoint);\n'
        '    return g != g_none && impl_->available(g);\n',
        '    const Group g = group_of(codepoint);\n'
        '    if (g == g_none)\n'
        '        return false;\n'
        '    if (g == g_cjk)\n'
        '        return impl_->cjk_glyph(codepoint);\n'
        '    return impl_->available(g);\n',
        'CJK handles',
    ),
)
CJK_HEADER_OLD = (
    ' * Indic scripts use Noto faces embedded in the binary; Chinese, Japanese and\n'
    ' * Korean use the Noto Sans CJK files in /data/evoplayer/fonts when they are\n'
    ' * there (4-8 MB each, too big to embed).\n'
)
CJK_HEADER_NEW = (
    ' * Indic scripts use Noto faces embedded in the binary. Chinese, Japanese and\n'
    ' * Korean use that same on-demand atlas. The build embeds Noto Sans CJK\n'
    ' * subset faces, and a file in /data/evoplayer/fonts still wins.\n'
)


def apply_text_patches(text, patches):
    """Apply anchored replacements. A second call leaves patched text unchanged."""
    for old, new, label in patches:
        if new in text:
            continue
        if text.count(old) != 1:
            raise RuntimeError('Pinned source anchor changed: ' + label)
        text = text.replace(old, new, 1)
    return text


def patch_cjk_complex(text):
    """Embed CJK faces in the on-demand subtitle path and skip missing scalars."""
    return apply_text_patches(text, CJK_COMPLEX_PATCHES)


def patch_cjk_complex_header(text):
    """Point the complex-text comment at the embedded CJK faces."""
    return apply_text_patches(text, ((CJK_HEADER_OLD, CJK_HEADER_NEW, 'CJK header'),))


def freetype_build_flags():
    """Return (cflags, libs) for a host program that reads fonts with FreeType."""
    cflags = subprocess.run(['pkg-config', '--cflags', 'freetype2'], capture_output=True, text=True)
    libs = subprocess.run(['pkg-config', '--libs', 'freetype2'], capture_output=True, text=True)
    if cflags.returncode != 0 or libs.returncode != 0:
        detail = (cflags.stderr or libs.stderr or 'pkg-config failed').strip()
        raise RuntimeError('FreeType development files are required to check CJK faces. ' + detail)
    return cflags.stdout.split(), libs.stdout.split()


def verify_cjk_coverage(font_paths):
    """Fail the build when a pinned face set drops a common subtitle scalar.

    The result is cached from the checker source, the code point list and the
    face checksums. A second build with the same inputs does not recheck.
    """
    import cjk_subset
    codes = sorted(cjk_subset.cjk_codepoints())
    listing = '\n'.join(format(code, 'X') for code in codes) + '\n'
    checker = ROOT / 'scripts/cjk_glyph_check.cpp'
    stamp = {
        'checker_sha256': hashlib.sha256(checker.read_bytes()).hexdigest(),
        'codepoints_sha256': hashlib.sha256(listing.encode()).hexdigest(),
        'fonts': [digest(path) for path in font_paths],
    }
    stamp_path = CACHE / 'noto-cjk-coverage.stamp.json'
    if stamp_path.is_file():
        cached = json.loads(stamp_path.read_text())
        if all(cached.get(key) == stamp[key] for key in stamp):
            print('CJK coverage cache hit:', cached.get('covered'), 'of', cached.get('total'))
            return
    WORK.mkdir(parents=True, exist_ok=True)
    list_path = WORK / 'cjk-codepoints.txt'
    list_path.write_text(listing)
    compiler = host_cxx()
    cflags, libs = freetype_build_flags()
    tool = WORK / 'cjk_glyph_check'
    run([compiler, '-O2', '-std=c++17', *cflags, '-o', tool, checker, *libs])
    proc = subprocess.run([str(tool), str(list_path), *[str(path) for path in font_paths]],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or 'CJK coverage check failed').strip()
        raise RuntimeError('CJK faces do not cover the subtitle set:\n' + detail[-2000:])
    print(proc.stdout.strip())
    covered, _, total = proc.stdout.strip().split()[1:]
    stamp['covered'] = int(covered)
    stamp['total'] = int(total)
    stamp_path.write_text(json.dumps(stamp, indent=2) + '\n')


def install_cjk_fonts(evo):
    """Copy the pinned CJK faces into the title and teach the HUD to use them."""
    fonts = []
    for item in CJK_FONTS:
        _pin, cached = fetch(item['id'])
        fonts.append(cached)
    verify_cjk_coverage(fonts)
    dest = evo / 'projects/evoplayer/assets/fonts'
    if not dest.is_dir():
        raise RuntimeError('EVO is missing assets/fonts')
    total = 0
    for item, src in zip(CJK_FONTS, fonts):
        target = dest / item['file']
        if not target.is_file() or digest(target) != digest(src):
            shutil.copyfile(src, target)
        total += target.stat().st_size
    notice_src = ROOT / 'scripts/noto-cjk-notice.txt'
    notice = dest / 'NotoCJK-NOTICE.txt'
    if not notice.is_file() or notice.read_bytes() != notice_src.read_bytes():
        shutil.copyfile(notice_src, notice)
    source = evo / 'projects/evoplayer/ui_kit/src/evo_hui_complex.cpp'
    header = evo / 'projects/evoplayer/ui_kit/include/evo_hui_complex.hpp'
    source.write_text(patch_cjk_complex(source.read_text()))
    header.write_text(patch_cjk_complex_header(header.read_text()))
    print('CJK faces', total, 'bytes, on-demand atlas', '2048x2048')


def provide_hui(evo):
    """Install the pinned EVO UI kit where the Makefile expects its submodule.

    EVO v0.12.0 records third_party/ps5-homebrew-ui as a git submodule, and a
    pinned codeload archive contains only the empty directory. The adapter
    unpacks the kit's own pinned archive instead (see deps.lock). It then
    rebakes the HUD fallback font with Thai and Devanagari (#18) and embeds
    CJK faces for the on-demand subtitle atlas."""
    pin, archive = fetch('ps5-homebrew-ui-source')
    dest = evo / 'third_party/ps5-homebrew-ui'
    if dest.exists():
        shutil.rmtree(dest)
    with tarfile.open(archive) as t:
        t.extractall(evo / 'third_party', filter='data')
    (evo / 'third_party' / pin['directory']).rename(dest)
    for rel in ('src/gfx/draw_list.cpp', 'src/gfx/font.cpp', 'src/gfx/triangulate.cpp',
                'src/audio/cues.cpp', 'src/audio/mixer.cpp', 'src/audio/wav.cpp'):
        if not (dest / rel).is_file():
            raise RuntimeError('ps5-homebrew-ui is missing ' + rel + ' - layout changed')
    for sub in ('src/ui', 'src/ui/components', 'src/core'):
        if not any((dest / sub).glob('*.cpp')):
            raise RuntimeError('ps5-homebrew-ui has no sources under ' + sub)
    bake_subtitle_fallback(dest, evo)
    install_cjk_fonts(evo)


def fix_network_reader(text):
    """Keep provider range reads on FFmpeg's bounded single-connection reader."""
    start = text.index('    /*\n     * A big file over HTTP is fetched by several connections at once.')
    # Stop at the HTTP block, not avformat_open_input: the new SMB and NTFS
    # readers between them own their custom IO and must remain intact.
    if text.count('        ctx->pio = evo_pio_open(') != 1:
        raise RuntimeError('Pinned parallel reader block changed')
    body = text.index('        ctx->pio = evo_pio_open(', start)
    end = text.index('    }\n\n', body) + len('    }\n\n')
    block = text[start:end]
    if block.count('ctx->pio = evo_pio_open(') != 1 or block.count('AVFMT_FLAG_CUSTOM_IO') != 1:
        raise RuntimeError('Pinned parallel reader block changed')
    text = text[:start] + '''    /* Six range readers caused HTTP429 storms after provider seeks (#4).
     * Use FFmpeg's reader: one connection, provider headers, range seeks and
     * the bounded retry policy below. The custom reader bypassed that policy. */
    if (ctx->is_network)
        SIO_BC("P8_01d1_HTTP_READER", "single connection");

''' + text[end:]
    anchor = '    av_dict_set(opts, "reconnect_delay_max", "2", 0);'
    if text.count(anchor) != 1:
        raise RuntimeError('Pinned network retry policy changed')
    return text.replace(anchor, anchor + '\n'
        '    av_dict_set(opts, "reconnect_on_http_error", "429,503", 0);\n'
        '    av_dict_set(opts, "respect_retry_after", "1", 0);')


def fix_provider_seek(demux, controller):
    # EVO v0.12.0 handles provider seeks itself: the demuxer guard does not
    # require a local media path, and the controller resumes instead of
    # announcing a refused seek (hardware sessions, 2026-10-01). Verify the
    # pinned forms and leave both sources unchanged.
    guard = '(video_stream_index < 0 && audio_stream_index < 0)\n    ) {'
    if demux.count(guard) != 1:
        raise RuntimeError('Pinned provider seek guard changed')
    refused = '    if (!prospero_request_inplace_seek(targetSeconds, 0)) {'
    handled = '        return;\n    }\n    pp_playback_notify_seek_begin(&g_pp_pb, targetUs);'
    if controller.count(refused) != 1 or controller.count(handled) != 1:
        raise RuntimeError('Pinned provider seek controller changed')
    return demux, controller


def instrument_loopback_server(source):
    """Log proxy socket, bind, listen and browser accept as separate results."""
    replacements = (
        ('    int fd = socket(AF_INET, SOCK_STREAM, 0);\n'
         '    if (fd < 0) { LOG("server: socket errno=%d", errno); return; }',
         '    int fd = socket(AF_INET, SOCK_STREAM, 0);\n'
         '    if (fd < 0) { LOG("server: socket failed errno=%d", errno); return; }\n'
         '    LOG("server: socket ok fd=%d", fd);'),
        ('    if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0 || listen(fd, 16) != 0) {\n'
         '        LOG("server: bind/listen 127.0.0.1:%d failed errno=%d", s_port, errno);\n'
         '        close(fd);\n'
         '        return;\n'
         '    }',
         '    if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0) {\n'
         '        int error = errno;\n'
         '        LOG("server: bind failed port=%d errno=%d", s_port, error);\n'
         '        close(fd);\n'
         '        return;\n'
         '    }\n'
         '    LOG("server: bind ok 127.0.0.1:%d", s_port);\n'
         '    if (listen(fd, 16) != 0) {\n'
         '        int error = errno;\n'
         '        LOG("server: listen failed port=%d errno=%d", s_port, error);\n'
         '        close(fd);\n'
         '        return;\n'
         '    }\n'
         '    LOG("server: listen ok port=%d", s_port);'),
        ('        int c = accept(s_listen_fd, NULL, NULL);\n'
         '        if (c >= 0 && s_srv_stop) { close(c); break; }',
         '        int c = accept(s_listen_fd, NULL, NULL);\n'
         '        if (c >= 0 && s_srv_stop) { close(c); break; }\n'
         '        if (c >= 0) LOG("server: connection accepted");'),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError('Pinned EVO loopback server anchor changed')
        source = source.replace(old, new)
    return source


def bypass_loopback_origin_preflight(source):
    """Open EVO's browser so it can probe the local proxy without its UI server."""
    old = '''        if (s_check_rc < 0) {
            char m[256];
'''
    # adapt() inserts this only for a diagnostic build. A preprocessor guard
    # would also need a compiler definition; the earlier guard had none and
    # silently left the missing-server preflight active.
    new = '''        if (s_check_rc < 0) {
            LOG("preflight bypassed for unpromoted loopback diagnostic");
            s_check_rc = 1;
        }
        if (s_check_rc < 0) {
            char m[256];
'''
    if source.count(old) != 1:
        raise RuntimeError('Pinned EVO preflight anchor changed')
    return source.replace(old, new)


def title_ui_sources(web, provider):
    """Serve the packaged page on EVO's existing listener for the Nuvio profile."""
    replacements = (
        ('#include "evo_webui.h"', '#include "evo_webui.h"\n#include "local_ui.h"'),
        ('        else\n            proxy_request(fd, req, got, hl, method, path);',
         '''        else if (!strcmp(s_hook_profile, "nuvio")) {
            char tag[96];
            size_t tag_len = is_html_entry(path) ? hook_tag(tag, sizeof tag) : 0;
            int status = nuvio_local_ui_send(fd,
                nuvio_local_ui_root(), method, path, tag, tag_len);
            LOG("title-ui: response status=%d", status);
        } else
            proxy_request(fd, req, got, hl, method, path);'''),
        ('    if (s_local_root[0]) {\n        s_check_rc = 1;',
         '''    /* Keep the configured origin as the existing browser-storage key;
     * packaged Nuvio needs no external host preflight. */
    if (!strcmp(s_hook_profile, "nuvio") || s_local_root[0]) {
        s_check_rc = 1;'''),
    )
    for old, new in replacements:
        if web.count(old) != 1:
            raise RuntimeError('Pinned title-local UI anchor changed')
        web = web.replace(old, new)
    # Fresh installations must be configured before any external helper runs.
    old = "    g_host[0] = '\\0';\n    g_port = NUVIO_DEFAULT_PORT;"
    if provider.count(old) != 1:
        raise RuntimeError('Pinned Nuvio provider initialization changed')
    provider = provider.replace(old, '    snprintf(g_host, sizeof g_host, "127.0.0.1");\n    g_port = 4173;')
    return web, provider


def startup_status(web, auto_bootstrap):
    """Give the Nuvio loading screen the reason startup stopped.

    Every startup failure used to leave the same "Opening Nuvio Pro" screen.
    Messages are fixed text plus numbers, so they are safe as RML markup.
    """
    again = 'Close Nuvio Pro and open it again.'
    helpers = r"""
static char s_nuvio_failure[384];
static void nuvio_fail(const char *title, const char *detail)
{
    snprintf(s_nuvio_failure, sizeof s_nuvio_failure,
             "%s<br/><span class=\"nuvio-detail\">%s</span>", title, detail);
    LOG("startup: %s. %s", title, detail);
}
"""
    if auto_bootstrap:
        helpers += r"""static void nuvio_fail_bootstrap(const char *stage, int error)
{
    char detail[192];
    if (!strncmp(stage, "connect", 7)) {
        snprintf(detail, sizeof detail, "Start your jailbreak's ELF loader, then open Nuvio Pro again (%s, errno %d).", stage, error);
        nuvio_fail("No ELF loader answered on port 9021", detail);
    } else if (!strcmp(stage, "transfer")) {
        snprintf(detail, sizeof detail, "Run your jailbreak again, then open Nuvio Pro again (transfer, errno %d).", error);
        nuvio_fail("The ELF loader did not start the Nuvio helper", detail);
    } else {
        snprintf(detail, sizeof detail, "AGAIN (%s, errno %d)", stage, error);
        nuvio_fail("Nuvio Pro could not start its helper", detail);
    }
}
"""
    log = '#define LOG(...) do { evo_bt("web: " __VA_ARGS__); evo_boot_log_flush(); } while (0)\n'
    replacements = (
        ('#include "evo_webui.h"', '#include "evo_webui.h"\n#include "local_ui.h"\n#include "evo_jailbreak.h"\n#include <time.h>'),
        (log, log + helpers),
        ('        LOG("NO-GO at Initialize");\n',
         '        LOG("NO-GO at Initialize");\n'
         '        if (!strcmp(s_hook_profile, "nuvio")) nuvio_fail("The PS5 browser did not start", "AGAIN");\n'),
        # Without a listener or the packaged page, the browser would only show
        # a dead page until the watchdog closes it. Stop here and say why.
        ('    server_start();\n    evo_mkdir(evo_data_path("webui"));\n',
         '    if (!strcmp(s_hook_profile, "nuvio")) s_nuvio_failure[0] = \'\\0\';\n'
         '    server_start();\n'
         '    if (!strcmp(s_hook_profile, "nuvio")) {\n'
         '        if (s_listen_fd < 0) {\n'
         '            if (!s_nuvio_failure[0])\n'
         '                nuvio_fail("Nuvio Pro could not start its page server", "AGAIN See /data/nuvio/evo.log for details.");\n'
         '            s_state = P_OFF;\n'
         '            return;\n'
         '        }\n'
         '        const char *ui_root = nuvio_local_ui_root();\n'
         '        char ui_index[512];\n'
         '        snprintf(ui_index, sizeof ui_index, "%s/index.html", ui_root);\n'
         '        int webui_fd = open(ui_index, O_RDONLY);\n'
         '        if (webui_fd < 0) {\n'
         '            LOG("startup: webui check failed root=%s errno=%d", ui_root, errno);\n'
         '            nuvio_fail("Nuvio Pro is missing its webui folder",\n'
         '                       "Install PPSA99996 in a ShadowMountPlus folder, such as /data/homebrew or /mnt/ext1/homebrew on the M.2 drive.");\n'
         '            s_state = P_OFF;\n'
         '            return;\n'
         '        }\n'
         '        close(webui_fd);\n'
         '    }\n'
         '    evo_mkdir(evo_data_path("webui"));\n'),
        ('    LOG("sceWebBrowserDialogOpen -> 0x%08x", (unsigned)rc);\n    if (rc != 0) {\n',
         '    LOG("sceWebBrowserDialogOpen -> 0x%08x", (unsigned)rc);\n    if (rc != 0) {\n'
         '        if (!strcmp(s_hook_profile, "nuvio")) {\n'
         '            char detail[96];\n'
         '            snprintf(detail, sizeof detail, "AGAIN (0x%08x)", (unsigned)rc);\n'
         '            nuvio_fail("The PS5 browser did not open", detail);\n'
         '        }\n'),
        ('        LOG("open refused: the dialog module never loaded (0x%08x)", (unsigned)s_preload_rc);\n',
         '        LOG("open refused: the dialog module never loaded (0x%08x)", (unsigned)s_preload_rc);\n'
         '        if (!strcmp(s_hook_profile, "nuvio")) {\n'
         '            char detail[96];\n'
         '            snprintf(detail, sizeof detail, "AGAIN (0x%08x)", (unsigned)s_preload_rc);\n'
         '            nuvio_fail("The PS5 browser is not available", detail);\n'
         '        }\n'),
        # Page watchdog and lost-connection errors.
        ('    snprintf(s_error, sizeof s_error, "%s", msg);\n    s_error_pending = 1;\n',
         '    snprintf(s_error, sizeof s_error, "%s", msg);\n    s_error_pending = 1;\n'
         '    if (!strcmp(s_hook_profile, "nuvio"))\n'
         '        nuvio_fail("The Nuvio page did not load", "AGAIN See /data/nuvio/evo.log for details.");\n'),
    )
    for old, new in replacements:
        if web.count(old) != 1:
            raise RuntimeError('Pinned Nuvio startup status anchor changed')
        web = web.replace(old, new.replace('AGAIN', again))
    # Nuvio opens only after a jailbreak daemon lifts the title sandbox.
    # Without one, say so after a delay that covers a slow but healthy start.
    return web + r"""
const char *evo_nuvio_startup_status(void)
{
    static struct timespec start;
    if (s_nuvio_failure[0]) return s_nuvio_failure;
    if (evo_jailbreak_is_open()) return "Opening Nuvio Pro";
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    if (!start.tv_sec && !start.tv_nsec) start = now;
    if (now.tv_sec - start.tv_sec < 8) return "Opening Nuvio Pro";
    return "Waiting for the jailbreak to unlock storage<br/><span class=\"nuvio-detail\">"
           "Run etaHEN or another jailbreak daemon. Nuvio Pro continues when storage unlocks.</span>";
}
"""


def adapt(evo, loopback_diagnostic=False, title_ui=False, auto_bootstrap=False):
    """Keep the native player; open its existing Nuvio bridge at startup."""
    app = evo/'projects/evoplayer'
    param_path = app/'sce_sys/param.json'
    # The published title identity and content version live in one file so the
    # store catalog can read them from a release tag.
    identity = json.loads((ROOT/'sce_sys/param.json').read_text())
    if identity['titleId'] != TITLE:
        raise RuntimeError('sce_sys/param.json titleId does not match '+TITLE)
    param = json.loads(param_path.read_text())
    param['titleId'] = identity['titleId']
    param['conceptId'] = identity['conceptId']
    param['contentId'] = identity['contentId']
    param['contentVersion'] = identity['contentVersion']
    param['applicationCategoryType'] = identity['applicationCategoryType']
    param['contentBadgeType'] = identity['contentBadgeType']
    param['localizedParameters']['en-US']['titleName'] = identity['localizedParameters']['en-US']['titleName']
    param.setdefault('pubtools', {})['loudnessSnd0'] = identity['pubtools']['loudnessSnd0']
    param_path.write_text(json.dumps(param, indent=2)+'\n')
    # Separate settings from an installed EVO. All persistent writes stay /data.
    for p in app.rglob('*'):
        if p.suffix in ('.c', '.h', '.cpp', '.hpp'):
            s = p.read_text()
            if '/data/evoplayer' in s or '/download0/evoplayer' in s:
                p.write_text(s.replace('/data/evoplayer', '/data/nuvio').replace('/download0/evoplayer', '/download0/nuvio'))
    replace_once(app/'core/src/Application.cpp',
                 '''static void EnsureDataDirectories() {
    mkdir("/data", 0777);
    mkdir(evo_data_dir(), 0777);
}''',
                 '''static void EnsureDataDirectories() {
    evo_mkdir("/data");
    evo_mkdir(evo_data_dir());
    evo_mkdir(evo_data_path("webui"));
}''')
    replace_once(app/'core/src/Application.cpp',
                 '        evo_webui_pump();   /* #101: the system browser, when a web UI is open */',
                 '''        /* Nuvio starts once its durable settings are reachable. Existing
         * EVO code owns browser, playback handoff and shutdown lifetimes. */
        static bool nuvio_opened = false;
        if (!nuvio_opened && evo_jailbreak_is_open()) {
            const evo_provider_t *nv = evo_provider_find("nuvio");
            if (nv && nv->is_configured() &&
                evo_webui_open_ex(nv->web_ui_url(), "/", "nuvio") == 0)
                nuvio_opened = true;
        }
        evo_webui_pump();   /* #101: the system browser, when a web UI is open */
        if (evo_webui_take_settings_requested() && m_screenManager) {
            m_screenManager->navigateTo(ScreenId::Settings);
        }''')
    replace_once(app/'src/evo_webui.c',
                 '2, 108,  0, 1812, 1080, 0x0, 0x0',
                 '2,   0,  0, 1920, 1080, 0x0, 0x0')
    web = app/'src/evo_webui.c'
    web_source = instrument_loopback_server(web.read_text())
    if loopback_diagnostic:
        web_source = bypass_loopback_origin_preflight(web_source)
    if title_ui:
        provider = app/'addons/src/provider_nuvio.c'
        web_source, provider_source = title_ui_sources(web_source, provider.read_text())
        provider.write_text(provider_source)
        for name in ('local_ui.c', 'local_ui.h', 'webui_roots.h'):
            shutil.copyfile(ROOT/'scripts'/name, app/'src'/name)
        # Reuse the payload server's path and MIME helpers. Its listener is
        # never called by the title; requests use EVO's existing connection.
        shutil.copyfile(ROOT/'scripts/ui_server.c', app/'src/nuvio_ui_files.c')
        replace_once(app/'Makefile',
                     'C_SRCS := $(PP_SRCS) $(UI_SRCS) $(MEDIA_SRCS) $(ADDON_SRCS)',
                     'C_SRCS := $(PP_SRCS) $(UI_SRCS) $(MEDIA_SRCS) $(ADDON_SRCS) src/local_ui.c src/nuvio_ui_files.c')
    if auto_bootstrap:
        web_source = web_source.replace('#include "evo_webui.h"', '#include "evo_webui.h"\n#include "bootstrap.h"')
        anchor = '    if (s_listen_fd >= 0) return;\n    int fd = socket(AF_INET, SOCK_STREAM, 0);'
        if web_source.count(anchor) != 1:
            raise RuntimeError('Pinned server bootstrap anchor changed')
        web_source = web_source.replace(anchor, '''    if (s_listen_fd >= 0) return;
    if (!strcmp(s_hook_profile, "nuvio")) {
        LOG("bootstrap: promotion requested");
        int rc = nuvio_bootstrap();
        if (rc == 0) LOG("bootstrap: promotion verified errno=0");
        else {
            int error = errno;
            LOG("bootstrap: promotion failed stage=%s errno=%d", nuvio_bootstrap_stage(), error);
            nuvio_fail_bootstrap(nuvio_bootstrap_stage(), error);
            return;
        }
    }
    int fd = socket(AF_INET, SOCK_STREAM, 0);''')
        for name in ('bootstrap.c', 'bootstrap.h'):
            shutil.copyfile(ROOT/'scripts'/name, app/'src'/name)
        replace_once(app/'Makefile', 'src/local_ui.c src/nuvio_ui_files.c',
                     'src/local_ui.c src/nuvio_ui_files.c src/bootstrap.c')
    web.write_text(startup_status(web_source, auto_bootstrap))
    header = app/'include/evo_webui.h'
    header.write_text(header.read_text()+'\n#ifdef __cplusplus\nextern "C"\n#endif\nconst char *evo_nuvio_startup_status(void);\n')
    # Provider sources intentionally have no local path. Check the demuxer,
    # and never announce an unqueued seek to the playback state machine.
    demux = app/'media/src/evo_demux.c'
    controller = app/'core/src/services/PlaybackController.cpp'
    fixed = fix_provider_seek(demux.read_text(), controller.read_text())
    demux.write_text(fixed[0]); controller.write_text(fixed[1])
    stream_io = app/'media/src/evo_stream_io.c'
    stream_io.write_text(fix_network_reader(stream_io.read_text()))
    # Keep diagnostics available without a USB stick on this console.
    replace_once(app/'src/evo_boot_log.c', '"/mnt/usb0/evo.log"', '"/data/nuvio/evo.log"')
    # Omit the unused AV1 add-on archive from the baseline pacbrew build.
    # No stub decoder is substituted; FFmpeg's available decoders are unchanged.
    script = evo/'scripts/package-app.sh'
    s = script.read_text()
    start = s.index('    # Auto-install libdav1d into sysroot if missing')
    end = s.index('    # Static archives EVO links', start)
    s = s[:start]+s[end:]
    s = s.replace('libswscale libdav1d \\', 'libswscale \\')
    # Only the host converter uses host zlib. Target libraries remain unchanged.
    if os.uname().sysname == 'Darwin':
        zlib = 'ZLIB_ARCHIVE="${NUVIO_MAC_SDK}/usr/lib/libz.tbd"'
        s = s.replace('clang++ -std=c++20', '/usr/bin/clang++ -std=c++20')
        s = s.replace('readelf -lW', 'llvm-readelf -lW')
    else:
        zlib = 'ZLIB_ARCHIVE="$(pkg-config --variable=libdir zlib)/libz.a"'
    # Drain readelf output so an early awk exit does not trigger SIGPIPE under pipefail.
    s = s.replace("awk '$1==\"LOAD\" && $7==\"R\" && $8 ~ /^0x/ {print $2; exit}'",
                  "awk '!seen && $1==\"LOAD\" && $7==\"R\" && $8 ~ /^0x/ {print $2; seen=1}'")
    s = s.replace('eval "$("${SCRIPTS_DIR}/setup-native-app-deps.sh")"',
                  zlib)
    s = s.replace('-I "${ZLIB_INCLUDE}"', '')
    s = '\n'.join('echo "Installable inventory is recorded in build.json."'
                  if line.startswith('find "${APPDIR}" -type f -printf') else line
                  for line in s.splitlines()) + '\n'
    s = s.replace('BUILD_SHA="$(git -C "${EVO}" rev-parse --short=8 HEAD 2>/dev/null || echo unknown)"',
                  'BUILD_SHA="'+fetch('evo-player-nuvio-source')[0]['commit'][:8]+'-nuvio"')
    script.write_text(s)
    disable_stock_services(evo)


def disable_stock_services(evo):
    """Do not install another title's updates or launch a new disk payload."""
    app = evo/'projects/evoplayer'
    updater = app/'addons/src/evo_updater.c'
    text = updater.read_text()
    # Keep the upstream API, including its pure formatting/version functions,
    # but remove every network, staging and replacement entry point.
    for name, result in (('evo_updater_check', '(void)prefer_pro;\n    set_state(EVO_UPD_FAILED, "Install updates from Nuvio Pro releases");'),
                         ('evo_updater_download', 'return 0;'),
                         ('evo_updater_cancel', ''),
                         ('evo_updater_apply', 'return 0;')):
        start = text.index('{', text.index('\n' + ('void ' if name in (
            'evo_updater_check', 'evo_updater_cancel') else 'int ') + name))
        end = text.index('\n}', start) + 2
        text = text[:start] + '{\n    ' + result + '\n}' + text[end:]
    updater.write_text(text)
    # The new unauthenticated LAN log/phone-input server is not part of Nuvio's
    # loopback browser bridge. Keep it inactive, including manual bind probes.
    log_server = app/'src/evo_log_server.c'
    text = log_server.read_text()
    for name, result in (('void evo_log_server_start', ''),
                         ('int evo_log_server_probe_port', '(void)port; return ENOTSUP;')):
        start = text.index('{', text.index('\n' + name))
        end = text.index('\n}', start) + 2
        text = text[:start] + '{\n    ' + result + '\n}' + text[end:]
    log_server.write_text(text)
    replace_once(app/'core/src/Application.cpp',
        '                    evo_updater_check(evo_direct_mem_kernel_total_mb() > 12288);',
        '                    /* Nuvio releases are installed separately. */')
    ntfs = app/'src/evo_ntfs.c'
    text = ntfs.read_text()
    start = text.index('#ifdef EVO_APP_MODULE\n/* ---- disks through the helper payload')
    end = text.index('\n#endif', start) + len('\n#endif')
    text = text[:start] + '/* Nuvio does not launch the upstream NTFS disk helper. */' + text[end:]
    text = text.replace('#ifdef EVO_APP_MODULE\n    refresh_remote();\n#endif', '')
    ntfs.write_text(text)
    replace_once(app/'Makefile', '    src/generated/evo_ntfs_helper_elf.c \\\n', '')
    replace_once(evo/'scripts/package-app.sh',
        '    bash "${REPO_ROOT}/tools/gen_ntfs_helper.sh" || die "NTFS helper payload did not build"',
        '    # Nuvio does not build or embed the upstream NTFS disk helper.')


def patch_index(html):
    """Add the PS5 input bridge and a black first paint to Nuvio's index page.

    The PS5 browser paints its own document background before the Nuvio CSS
    applies. The white default flashes the whole screen when the browser
    reopens after playback, so the served page must be black from the first
    byte of <head>.

    The stylesheet stays a plain render-blocking <link>. A `media="print"`
    link switched to `all` on load paints earlier, but the console's browser
    then renders Nuvio unstyled, so the pattern is not usable here.
    """
    if html.count('<head>') != 1 or html.count('</head>') != 1:
        raise RuntimeError('Pinned UI index head anchors changed')
    if 'ps5-input.js' in html:
        raise RuntimeError('UI index already carries the PS5 bridge')
    html = html.replace('<title>Nuvio TV</title>', '<title>Nuvio Pro</title>')
    html = html.replace('<head>',
                        '<head>\n    <style>html,body{background-color:#000;margin:0}'
                        'html,body,body *{cursor:none!important}'
                        '#__evoClose{display:none!important}</style>')
    return html.replace('</head>', '<script src="ps5-input.js"></script></head>')


def configure_ui(ui):
    # Use the pinned release's browser login and metadata configuration only.
    # Never copy a privileged Supabase key or unrelated client credentials.
    _, package = fetch('nuvio-official-tv-config')
    with zipfile.ZipFile(package) as z:
        raw = z.read('nuvio.env.js').decode()
    match = re.search(r'var values = (\{.*?\});', raw, re.S)
    if not match:
        raise RuntimeError('Pinned public runtime config changed')
    official = json.loads(match[1])
    key = official.get('NUVIO_SUPABASE_ANON_KEY', '')
    if not key.startswith('sb_publishable_'):
        parts = key.split('.')
        if len(parts) != 3 or json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4))).get('role') != 'anon':
            raise RuntimeError('Release does not contain an anonymous publishable key')
    path = ui/'nuvio.env.js'
    source = path.read_text()
    for name in ('NUVIO_SUPABASE_URL', 'NUVIO_SUPABASE_ANON_KEY',
                 'NUVIO_SUPABASE_FALLBACK_URL', 'TV_LOGIN_WEB_BASE_URL',
                 'DEVICE_LOGIN_WEB_BASE_URL', 'AVATAR_PUBLIC_BASE_URL',
                 'TMDB_API_KEY', 'TRAKT_CLIENT_ID'):
        value = official.get(name, '')
        if name.endswith('_URL') and value and not value.startswith('https://'):
            raise RuntimeError('Official public configuration must use HTTPS')
        source, count = re.subn(r'"'+name+r'":\s*"[^"\n]*"', lambda m: json.dumps(name)+': '+json.dumps(value), source)
        if count != 1:
            raise RuntimeError('Pinned UI runtime config anchor changed')
    path.write_text(source)
    shutil.copyfile(ROOT/'scripts/ps5-input.js', ui/'ps5-input.js')
    index = ui/'index.html'
    index.write_text(patch_index(index.read_text()))


def stamp_fork_version(nv):
    """Publish this fork's VERSION inside the browser bundle, not upstream 1.4.x."""
    version = (ROOT/'VERSION').read_text().strip()
    if not version:
        raise RuntimeError('VERSION is empty')
    package_path = nv/'package.json'
    package = json.loads(package_path.read_text())
    package['version'] = version
    package_path.write_text(json.dumps(package, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ui-only', action='store_true')
    ap.add_argument('--auto-bootstrap', type=int, metavar='LOADER_PORT',
                    help='Embed promotion helper and submit it to the specified loopback loader port')
    ap.add_argument('--auth-profile', choices=('default', 'sdk-install-app'), default='default',
                    help='Signing metadata for a controlled permission test')
    ap.add_argument('--title-ui', action='store_true',
                    help='Serve packaged UI files inside the title for a single-install test')
    args = ap.parse_args()
    if args.auto_bootstrap is not None and (not args.title_ui or not 1 <= args.auto_bootstrap <= 65535):
        ap.error('--auto-bootstrap requires --title-ui and a valid loader port')
    loopback_diagnostic = os.environ.get('NUVIO_UNPROMOTED_LOOPBACK_DIAGNOSTIC') == '1'
    CACHE.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    nv = source('nuvio-tv-source')
    polish.patch_nuvio(nv)
    stamp_fork_version(nv)
    run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=nv)
    run(['npm', 'run', 'build'], cwd=nv)
    ui = WORK/'ui'
    shutil.copytree(nv/'dist', ui, dirs_exist_ok=True)
    configure_ui(ui)
    if args.ui_only:
        print('Host UI built:', ui)
        return
    host = os.uname().sysname
    if host not in ('Linux', 'Darwin'):
        raise RuntimeError('The native host adapter requires Linux or macOS.')
    sdk = WORK/'sdk/ps5-payload-sdk'
    env = os.environ.copy()
    if host == 'Darwin':
        llvm = subprocess.check_output(['brew', '--prefix', 'llvm'], text=True).strip()
        core = subprocess.check_output(['brew', '--prefix', 'coreutils'], text=True).strip()
        env.setdefault('LLVM_CONFIG', llvm+'/bin/llvm-config')
        env['NUVIO_MAC_SDK'] = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
        env['PATH'] = core+'/libexec/gnubin'+os.pathsep+env['PATH']
    else:
        env.setdefault('LLVM_CONFIG', shutil.which('llvm-config-19') or shutil.which('llvm-config') or '')
    if not env['LLVM_CONFIG']:
        raise RuntimeError('LLVM not found. Install clang, lld and llvm development tools; set LLVM_CONFIG if needed.')
    llvm_bin = subprocess.check_output([env['LLVM_CONFIG'], '--bindir'], text=True).strip()
    env['PATH'] = os.pathsep.join([llvm_bin, str(sdk/'bin'), env['PATH']])
    env['PS5_PAYLOAD_SDK'] = str(sdk)
    env['PS5_LLD'] = str(Path(llvm_bin)/'ld.lld')
    if not Path(env['PS5_LLD']).is_file():
        if host == 'Darwin':
            lld = subprocess.check_output(['brew', '--prefix', 'lld'], text=True).strip()
            env['PS5_LLD'] = str(Path(lld)/'bin/ld.lld')
        if not Path(env['PS5_LLD']).is_file():
            raise RuntimeError('ld.lld not found. Install lld for the selected LLVM toolchain.')
    _, sdk_zip = fetch('ps5-payload-sdk-prebuilt')
    with zipfile.ZipFile(sdk_zip) as z:
        z.extractall(WORK/'sdk')
    _, ports = fetch('nuvio-pacbrew')
    with tarfile.open(ports) as t:
        prefix = 'opt/ps5-payload-sdk/target/user/homebrew/'
        t.extractall(WORK/'ports', members=[m for m in t.getmembers() if m.name.startswith(prefix)], filter='data')
    shutil.copytree(WORK/'ports/opt/ps5-payload-sdk/target/user/homebrew', sdk/'target/user/homebrew', dirs_exist_ok=True)
    # v0.43's ZIP does not preserve executable permissions for all host wrappers.
    for p in (sdk/'bin').iterdir():
        if p.is_file():
            p.chmod(p.stat().st_mode | 0o111)
    install_ffmpeg(sdk, env)
    evo = source('evo-player-nuvio-source')
    provide_hui(evo)
    adapt(evo, loopback_diagnostic=loopback_diagnostic, title_ui=args.title_ui, auto_bootstrap=args.auto_bootstrap is not None)
    polish.apply(evo, nv)
    import native_remote
    native_remote.patch_native(evo / 'projects/evoplayer')
    patches.write_patch(fetch('evo-player-nuvio-source')[1], evo, ROOT/'patches/evo.patch')
    patches.write_patch(fetch('nuvio-tv-source')[1], nv, ROOT/'patches/nuvio.patch')
    bootstrap_metadata = None
    if args.auto_bootstrap is not None:
        payload = WORK/'bootstrap-promote.elf'
        run([sdk/'bin/prospero-clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
             ROOT/'scripts/promote.c', '-lkernel_sys', '-lkernel_web', '-o', payload], env=env)
        import elfcheck
        elfcheck.validate(str(payload))
        raw = payload.read_bytes()
        if len(raw) > 1048576:
            raise RuntimeError('Bootstrap ELF exceeds the transfer bound')
        blob = evo/'projects/evoplayer/src/nuvio_bootstrap_blob.h'
        blob.write_text('#define NUVIO_BOOTSTRAP_PORT '+str(args.auto_bootstrap)+'\n'+
                        'static const unsigned char nuvio_bootstrap_elf[] = {\n'+
                        ',\n'.join(','.join('0x'+raw[i:i+16][j:j+1].hex() for j in range(len(raw[i:i+16])))
                                    for i in range(0,len(raw),16))+'\n};\n')
        bootstrap_metadata = {'loader_port': args.auto_bootstrap, 'payload_sha256': digest(payload),
                              'payload_bytes': len(raw)}
    # The app link expands "${PS5_SYSROOT}/lib"/*.so and relies on libkernel.so
    # coming before libkernel_web.so: with --as-needed the first stub that
    # satisfies a symbol is the one recorded in DT_NEEDED, and the module
    # imports exactly that library. A UTF-8 collation puts libkernel.so last,
    # so the title imported libkernel_web.prx and never started on the console.
    # C collation restores libkernel.prx. Do not remove this.
    env['LC_ALL'] = 'C'
    run(['bash', evo/'scripts/package-app.sh'], cwd=evo, env=env)
    auth_profile = None
    if args.auth_profile == 'sdk-install-app':
        # This is metadata from a pinned public example, not inferred capability
        # bits. Hardware must establish whether the resident HEN honours it.
        profile_source = sdk/'samples/install_app/Makefile'
        auth_profile = sdk_install_auth_profile(profile_source.read_text())
        tool = evo/'output/app/.build/host/ps5-native-tool'
        run([tool, 'self', '--sign', '--in', evo/'output/app/.build/eboot.elf',
             '--out', evo/'output/app'/TITLE/'eboot.bin', '--magic', '0x1D3D154F',
             '--authority', auth_profile['authority'], '--auth-info', auth_profile['auth_info']])
        run([tool, 'self', '--inspect', '--file', evo/'output/app'/TITLE/'eboot.bin'])
        auth_profile = {**auth_profile, 'source': 'SDK samples/install_app/Makefile',
                        'source_sha256': digest(profile_source)}
    # Reuse the reviewed, fixed-purpose controls with Nuvio's own identity.
    control = (ROOT/'vendor/control.c').read_text().replace('AURORA', 'NUVIO').replace('Aurora', 'Nuvio').replace('aurora', 'nuvio').replace('PPSA99998', TITLE)
    control = control.replace('PPSA99997', TITLE)
    control = control.replace('../../payloads/common/sha256.h', str(ROOT/'vendor/sha256.h'))
    (WORK/'control.c').write_text(control)
    for action in (1, 2, 3, 4, 5):
        inputs = [WORK/'control.c'] + ([ROOT/'vendor/sha256.c'] if action in (4, 5) else [])
        run([sdk/'bin/prospero-clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
             '-DNUVIO_CONTROL_ACTION='+str(action), *inputs, '-lkernel_sys', '-lkernel_web',
             '-lSceUserService', '-lSceSystemService', '-o', WORK/('control-'+str(action)+'.elf')], env=env)
    run([sdk/'bin/prospero-clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
         ROOT/'scripts/close.c', '-lkernel_sys', '-lkernel_web', '-o', WORK/'close.elf'], env=env)
    run([sdk/'bin/prospero-clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
         ROOT/'scripts/promote.c', '-lkernel_sys', '-lkernel_web',
         '-o', WORK/'promote.elf'], env=env)
    # One boot payload: it grants the title its network privilege and serves the
    # browser UI from the installed title folder (scripts/ui_server.c). That is
    # why no computer has to run an HTTP server on the same network.
    run([sdk/'bin/prospero-clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
         '-DNUVIO_WATCH', ROOT/'scripts/promote.c', ROOT/'scripts/ui_server.c',
         '-lkernel_sys', '-lkernel_web', '-o', WORK/'nuvio.elf'], env=env)
    dist = evo/'output/app'/TITLE
    (dist/'portable.txt').touch()
    # The upstream packager omits DDS. Assemble Shell media before hashing it.
    for name in ('pic0.dds', 'pic1.dds'):
        shutil.copyfile(ROOT/'assets/launch.dds', dist/'sce_sys'/name)
    shutil.copyfile(ROOT/'assets/snd0.at9', dist/'sce_sys/snd0.at9')
    # The UI travels inside the title folder, so one archive installs a working
    # app and the payload serves it over loopback with no LAN origin.
    shutil.rmtree(dist/'webui', ignore_errors=True)
    shutil.copytree(WORK/'ui', dist/'webui')
    receipt = {'title_id': TITLE, 'firmware_validation': '[UNKNOWN]',
               'ui_hosting': 'title' if args.title_ui else 'boot-payload',
               'automatic_bootstrap': bootstrap_metadata, 'auth_profile': args.auth_profile, 'auth_profile_metadata': auth_profile,
               'diagnostic_mode': 'unpromoted_loopback' if loopback_diagnostic else None,
               # Explicit names, not a glob: a stale helper from an earlier
               # build in the same work directory must not enter the receipt.
               'helpers': {name: digest(WORK/name) for name in (
                   'control-1.elf', 'control-2.elf', 'control-3.elf', 'control-4.elf', 'control-5.elf',
                   'promote.elf', 'nuvio.elf', 'close.elf')},
               'source_pins': {k: fetch(k)[0]['sha256'] for k in ('nuvio-tv-source','evo-player-nuvio-source','nuvio-pacbrew','ps5-payload-sdk-prebuilt','nuvio-official-tv-config','ffmpeg-source','ps5-homebrew-ui-source')},
               'files': {str(p.relative_to(dist)): digest(p) for p in dist.rglob('*') if p.is_file()}}
    (WORK/'build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('Native title:', dist, '\nReceipt:', WORK/'build.json')


if __name__ == '__main__':
    main()
