#!/usr/bin/python3
# -*- coding: UTF-8 -*-
# Author: Speefak

# ==============================================================================
# Configuration
# ==============================================================================
VDR_SOURCE_DIR  = '/mnt/fstab_virtiofs_tvh-storage/00_vdr'
TVH_RECORD_DIR  = '/mnt/fstab_virtiofs_tvh-storage/recordings'
FILE_PROCESSING = 'copy'          # 'copy' | 'move' | 'link'
DRY_RUN         = False           # True = nur anzeigen, nichts ausführen
TVH_API_BASE    = 'http://127.0.0.1:9981'
TVH_USER        = 'test'
TVH_PASS        = 'test'
TVH_LANGUAGE    = 'ger'
TVH_COMMENT     = 'VDR import'
# ==============================================================================

import json
import urllib.request
import urllib.parse
import datetime
import os
import shutil

API_URL = TVH_API_BASE + '/api/dvr/entry/create'

password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
password_mgr.add_password(None, TVH_API_BASE, TVH_USER, TVH_PASS)
opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(password_mgr))
urllib.request.install_opener(opener)

for dirPath, dirNames, fileList in os.walk(VDR_SOURCE_DIR):
    if 'info' not in fileList or '00001.ts' not in fileList:
        continue

    src_ts = os.path.join(dirPath, '00001.ts')
    video_title = video_subtitle = video_description = video_channelname = ""
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

    dt = datetime.datetime.fromtimestamp(video_startstmp)
    safe_title  = video_title.replace('/', '_').replace(':', '-')
    ts_filename = f"{safe_title}{dt.strftime('%Y-%m-%d%H-%M')}.ts"
    dst_ts      = os.path.join(TVH_RECORD_DIR, ts_filename)

    print(f"{video_title} | {video_subtitle}")
    print(f"  Kanal   : {video_channelname}  |  Start: {dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Quelle  : {src_ts}")
    print(f"  Ziel    : {dst_ts}")

    if DRY_RUN:
        print("  [DRY RUN] – keine Aktion\n")
        continue

    if os.path.exists(dst_ts):
        print("  ✗ Zieldatei existiert bereits, übersprungen\n")
        continue

    try:
        if FILE_PROCESSING == 'copy':
            shutil.copy2(src_ts, dst_ts)
            print(f"  ✓ Kopiert")
        elif FILE_PROCESSING == 'move':
            shutil.move(src_ts, dst_ts)
            print(f"  ✓ Verschoben")
        elif FILE_PROCESSING == 'link':
            os.link(src_ts, dst_ts)
            print(f"  ✓ Hardlink erstellt")
        else:
            print(f"  ✗ Unbekannter FILE_PROCESSING-Wert: {FILE_PROCESSING}")
            continue
    except Exception as e:
        print(f"  ✗ Dateioperation fehlgeschlagen: {e}\n")
        continue

    mask = {
        "enabled":     True,
        "start":       video_startstmp,
        "stop":        video_stopstmp,
        "channelname": video_channelname,
        "title":       {TVH_LANGUAGE: video_title},
        "subtitle":    {TVH_LANGUAGE: video_subtitle},
        "description": {TVH_LANGUAGE: video_description},
        "comment":     TVH_COMMENT,
        "files":       [{"filename": dst_ts}]
    }

    try:
        data = urllib.parse.urlencode({'conf': json.dumps(mask)}).encode('utf-8')
        req  = urllib.request.Request(API_URL, data=data,
               headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'uuid' in result:
                print(f"  ✓ TVheadend registriert: {result['uuid']}")
            else:
                print(f"  ✗ API Antwort: {result}")
    except Exception as e:
        print(f"  ✗ API Fehler: {e}")

    print()
