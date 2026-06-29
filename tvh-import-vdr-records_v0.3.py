#!/usr/bin/python3
# -*- coding: UTF-8 -*-
# ==============================================================================
# Script   : tvh-import-vdr-records_v0.1
# Version  : 0.3
# Author   : Speefak
# Licence  : (CC) BY-NC-SA
# ==============================================================================
# Description:
#   Imports VDR recordings into TVheadend by copying/moving/linking the TS file
#   into the TVheadend recordings directory and registering the entry via the
#   TVheadend REST API (dvr/entry/create).
#
# VDR recording structure expected:
#   <VDR_SOURCE_DIR>/<title>/<date.time.rec>/
#       00001.ts   - MPEG-TS stream
#       info       - metadata (title, subtitle, description, channel, timestamps)
#       index      - frame index (not used)
#
# TVheadend recording structure created:
#   <TVH_RECORD_DIR>/<Title>YYYY-MM-DDHH-MM.ts
#
# VDR info file keys used:
#   T  - title
#   S  - subtitle
#   D  - description
#   E  - event: <event_id> <start_unix> <duration_sec> [tableid] [version]
#   C  - channel: <channel_id> <channel_name>
#
# TVheadend API endpoint:
#   POST /api/dvr/entry/create
#   Body: conf=<json>  (application/x-www-form-urlencoded)
#   Auth: Digest MD5
#
# Requirements:
#   Python 3.x (stdlib only - no external dependencies)
#   TVheadend with API access enabled for the configured user
#
# Usage:
#   python3 tvh-import-vdr-records_v0.1 [OPTIONS]
#
# Options:
#   -vdrsrc DIR    VDR source directory
#   -tvhrc  DIR    TVheadend recordings directory
#   -user   USER   TVheadend API username
#   -pass   PASS   TVheadend API password
#   -fp     MODE   File processing mode: copy | move | link
#   -f             Force overwrite of existing destination files
#   -DR            Dry run - show actions without executing anything
#   -h / --help    Show help and exit
#
# Examples:
#   python3 tvh-import-vdr-records_v0.1
#       Run with all defaults defined in script header
#
#   python3 tvh-import-vdr-records_v0.1 -DR
#       Dry run - shows what would be done, no files moved, no API calls
#
#   python3 tvh-import-vdr-records_v0.1 -fp move -f
#       Move files, overwrite existing destinations
#
#   python3 tvh-import-vdr-records_v0.1 -vdrsrc /srv/vdr/recordings -tvhrc /srv/tvh/recordings
#       Custom source and target directories
#
#   python3 tvh-import-vdr-records_v0.1 -user admin -pass secret -fp link
#       Custom credentials, use hardlinks instead of copying
#
# Notes:
#   - Hardlinks (-fp link) only work if VDR source and TVheadend target are on
#     the same filesystem/partition.
#   - With -fp move the original VDR recording is removed after successful transfer.
#   - If a destination file already exists, the entry is skipped unless -f is set.
#   - video_description defaults to empty string if not present in info file.
#   - Filename special chars / and : are replaced with _ and - respectively.
# ==============================================================================

# ==============================================================================
# Default Configuration (overridable via CLI options)
# ==============================================================================
DEFAULT_VDR_SOURCE_DIR  = '/mnt/fstab_virtiofs_tvh-storage/00_vdr'
DEFAULT_TVH_RECORD_DIR  = '/mnt/fstab_virtiofs_tvh-storage/recordings'
DEFAULT_FILE_PROCESSING = 'copy'          # 'copy' | 'move' | 'link'
DEFAULT_TVH_API_BASE    = 'http://127.0.0.1:9981'
DEFAULT_TVH_USER        = 'test'
DEFAULT_TVH_PASS        = 'test'
DEFAULT_TVH_LANGUAGE    = 'ger'
DEFAULT_TVH_COMMENT     = 'VDR import'
# ==============================================================================

import json
import urllib.request
import urllib.parse
import datetime
import os
import shutil
import argparse

parser = argparse.ArgumentParser(
    prog='tvh-import-vdr-records_v0.1',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=(
        'Import VDR recordings into TVheadend.\n'
        'Copies/moves/links the TS stream to the TVheadend recordings directory\n'
        'and registers each entry via the TVheadend REST API.'
    ),
    epilog=(
        'Examples:\n'
        '  %(prog)s\n'
        '      Run with all defaults from script header\n\n'
        '  %(prog)s -DR\n'
        '      Dry run - show what would happen, no files touched, no API calls\n\n'
        '  %(prog)s -fp move -f\n'
        '      Move files into TVheadend dir, overwrite if destination exists\n\n'
        '  %(prog)s -vdrsrc /srv/vdr/rec -tvhrc /srv/tvh/rec\n'
        '      Custom source and target directories\n\n'
        '  %(prog)s -user admin -pass secret -fp link\n'
        '      Custom credentials, create hardlinks instead of copying\n'
    )
)
parser.add_argument('-vdrsrc', metavar='DIR',
                    default=DEFAULT_VDR_SOURCE_DIR,
                    help='VDR source directory (default: %(default)s)')
parser.add_argument('-tvhrc',  metavar='DIR',
                    default=DEFAULT_TVH_RECORD_DIR,
                    help='TVheadend recordings directory (default: %(default)s)')
parser.add_argument('-user',   metavar='USER',
                    default=DEFAULT_TVH_USER,
                    help='TVheadend API username (default: %(default)s)')
parser.add_argument('-pass',   metavar='PASS',
                    dest='tvh_pass', default=DEFAULT_TVH_PASS,
                    help='TVheadend API password (default: %(default)s)')
parser.add_argument('-fp',     metavar='MODE',
                    default=DEFAULT_FILE_PROCESSING, choices=['copy', 'move', 'link'],
                    help='File processing: copy | move | link (default: %(default)s)')
parser.add_argument('-f',      action='store_true',
                    help='Force overwrite of existing destination files')
parser.add_argument('-DR',     action='store_true',
                    help='Dry run - show actions without executing')
args = parser.parse_args()

VDR_SOURCE_DIR  = args.vdrsrc
TVH_RECORD_DIR  = args.tvhrc
FILE_PROCESSING = args.fp
TVH_USER        = args.user
TVH_PASS        = args.tvh_pass
FORCE           = args.f
DRY_RUN         = args.DR
TVH_API_BASE    = DEFAULT_TVH_API_BASE
TVH_LANGUAGE    = DEFAULT_TVH_LANGUAGE
TVH_COMMENT     = DEFAULT_TVH_COMMENT
API_URL         = TVH_API_BASE + '/api/dvr/entry/create'

print('=' * 60)
print('  tvh-import-vdr-records_v0.1  v0.7')
print('=' * 60)
print('  VDR source   : ' + VDR_SOURCE_DIR)
print('  TVH target   : ' + TVH_RECORD_DIR)
print('  TVH API      : ' + TVH_API_BASE)
print('  TVH user     : ' + TVH_USER)
print('  Processing   : ' + FILE_PROCESSING)
print('  Force        : ' + str(FORCE))
print('  Dry run      : ' + str(DRY_RUN))
print('=' * 60)
print()

password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
password_mgr.add_password(None, TVH_API_BASE, TVH_USER, TVH_PASS)
opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(password_mgr))
urllib.request.install_opener(opener)

stats = {'total': 0, 'ok': 0, 'skipped': 0, 'error': 0}

for dirPath, dirNames, fileList in os.walk(VDR_SOURCE_DIR):
    if 'info' not in fileList or '00001.ts' not in fileList:
        continue

    stats['total'] += 1
    src_ts = os.path.join(dirPath, '00001.ts')
    video_title = video_subtitle = video_description = video_channelname = ''
    video_startstmp = video_stopstmp = 0

    with open(os.path.join(dirPath, 'info'), encoding='utf-8', errors='ignore') as f:
        for line in f:
            entry = line.strip().split(' ', 1)
            if len(entry) < 2:
                continue
            key, value = entry[0].lower(), entry[1].strip()
            if   key == 't': video_title      = value
            elif key == 's': video_subtitle    = value
            elif key == 'd': video_description = value
            elif key == 'e':
                parts = value.split()
                if len(parts) >= 3:
                    video_startstmp = int(parts[1])
                    video_stopstmp  = video_startstmp + int(parts[2])
            elif key == 'c':
                video_channelname = value.split(' ', 1)[1] if ' ' in value else value

    dt          = datetime.datetime.fromtimestamp(video_startstmp)
    safe_title  = video_title.replace('/', '_').replace(':', '-')
    ts_filename = safe_title + dt.strftime('%Y-%m-%d%H-%M') + '.ts'
    dst_ts      = os.path.join(TVH_RECORD_DIR, ts_filename)

    print('  Title   : ' + video_title + (' | ' + video_subtitle if video_subtitle else ''))
    print('  Channel : ' + video_channelname + '  |  Start: ' + dt.strftime('%Y-%m-%d %H:%M'))
    print('  Source  : ' + src_ts)
    print('  Target  : ' + dst_ts)

    if DRY_RUN:
        print('  [DRY RUN] - keine Aktion')
        print()
        continue

    if os.path.exists(dst_ts):
        if not FORCE:
            print('  x Zieldatei existiert bereits, uebersprungen (-f zum Ueberschreiben)')
            print()
            stats['skipped'] += 1
            continue
        else:
            os.remove(dst_ts)
            print('  ! Zieldatei geloescht (force)')

    try:
        if FILE_PROCESSING == 'copy':
            shutil.copy2(src_ts, dst_ts)
            print('  + Kopiert')
        elif FILE_PROCESSING == 'move':
            shutil.move(src_ts, dst_ts)
            print('  + Verschoben')
        elif FILE_PROCESSING == 'link':
            os.link(src_ts, dst_ts)
            print('  + Hardlink erstellt')
    except Exception as e:
        print('  x Dateioperation fehlgeschlagen: ' + str(e))
        print()
        stats['error'] += 1
        continue

    mask = {
        'enabled':     True,
        'start':       video_startstmp,
        'stop':        video_stopstmp,
        'channelname': video_channelname,
        'title':       {TVH_LANGUAGE: video_title},
        'subtitle':    {TVH_LANGUAGE: video_subtitle},
        'description': {TVH_LANGUAGE: video_description},
        'comment':     TVH_COMMENT,
        'files':       [{'filename': dst_ts}]
    }

    try:
        data = urllib.parse.urlencode({'conf': json.dumps(mask)}).encode('utf-8')
        req  = urllib.request.Request(API_URL, data=data,
               headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'uuid' in result:
                print('  + TVheadend registriert: ' + result['uuid'])
                stats['ok'] += 1
            else:
                print('  x API Antwort: ' + str(result))
                stats['error'] += 1
    except Exception as e:
        print('  x API Fehler: ' + str(e))
        stats['error'] += 1

    print()

print('=' * 60)
print('  Gesamt: ' + str(stats['total']) +
      '  |  OK: ' + str(stats['ok']) +
      '  |  Uebersprungen: ' + str(stats['skipped']) +
      '  |  Fehler: ' + str(stats['error']))
print('=' * 60)
