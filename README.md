# tvh_addfile_vdr

Import VDR recordings into TVheadend – transfers the MPEG-TS stream into the
TVheadend recordings directory and registers each entry via the TVheadend REST API.

## Features

- Parses VDR `info` metadata files (title, subtitle, description, channel, timestamps)
- Transfers recordings via **copy**, **move**, or **hardlink**
- Registers each recording in TVheadend via `dvr/entry/create` API (Digest MD5 auth)
- Dry run mode to preview actions without touching any files or making API calls
- Force mode to overwrite existing destination files
- All parameters configurable via CLI; script header holds the defaults
- Summary statistics after each run
- No external dependencies – Python 3 stdlib only

---

## Requirements

- Python 3.x
- TVheadend with REST API access enabled for the configured user
- Network access from the host running the script to the TVheadend API port (default: 9981)

---

## VDR Recording Structure (input)

```
<VDR_SOURCE_DIR>/
  <Title>/
    <YYYY-MM-DD.HH.MM.SS.rec>/
      00001.ts    # MPEG-TS stream
      info        # metadata
      index       # frame index (not used)
```

### VDR `info` file keys used

| Key | Content |
|-----|---------|
| `T` | Title |
| `S` | Subtitle |
| `D` | Description |
| `E` | Event: `<id> <start_unix> <duration_sec> [tableid] [version]` |
| `C` | Channel: `<channel_id> <channel_name>` |

---

## TVheadend Recording Structure (output)

```
<TVH_RECORD_DIR>/
  <Title>YYYY-MM-DDHH-MM.ts
```

Filename special characters `/` and `:` are replaced with `_` and `-` respectively.

---

## TVheadend API

```
POST /api/dvr/entry/create
Body: conf=<json>  (application/x-www-form-urlencoded)
Auth: Digest MD5
```

The user configured in TVheadend must have **DVR** and **API** permissions.

---

## Installation

```bash
git clone https://github.com/Speefak/tvh_addfile_vdr.git
cd tvh_addfile_vdr
chmod +x tvh_addfile_vdr.py
```

Edit the default configuration block at the top of the script:

```python
DEFAULT_VDR_SOURCE_DIR  = '/mnt/vdr/recordings'
DEFAULT_TVH_RECORD_DIR  = '/mnt/tvh/recordings'
DEFAULT_FILE_PROCESSING = 'copy'          # 'copy' | 'move' | 'link'
DEFAULT_TVH_API_BASE    = 'http://127.0.0.1:9981'
DEFAULT_TVH_USER        = 'your_user'
DEFAULT_TVH_PASS        = 'your_pass'
```

---

## Usage

```
python3 tvh_addfile_vdr.py [OPTIONS]

Options:
  -vdrsrc DIR    VDR source directory
  -tvhrc  DIR    TVheadend recordings directory
  -user   USER   TVheadend API username
  -pass   PASS   TVheadend API password
  -fp     MODE   File processing mode: copy | move | link
  -f             Force overwrite of existing destination files
  -DR            Dry run - show actions without executing anything
  -h / --help    Show help and exit
```

---

## Examples

```bash
# Run with all defaults from script header
python3 tvh_addfile_vdr.py

# Dry run - preview what would happen, no files touched, no API calls
python3 tvh_addfile_vdr.py -DR

# Move files, overwrite existing destinations
python3 tvh_addfile_vdr.py -fp move -f

# Custom source and target directories
python3 tvh_addfile_vdr.py -vdrsrc /srv/vdr/recordings -tvhrc /srv/tvh/recordings

# Custom credentials, use hardlinks instead of copying
python3 tvh_addfile_vdr.py -user admin -pass secret -fp link

# Full example with all options
python3 tvh_addfile_vdr.py -vdrsrc /srv/vdr/rec -tvhrc /srv/tvh/rec \
    -user admin -pass secret -fp copy -f -DR
```

---

## Notes

- **Hardlinks** (`-fp link`) only work if VDR source and TVheadend target reside
  on the same filesystem/partition.
- **Move** (`-fp move`) removes the original VDR recording after successful transfer.
- If a destination file already exists, the entry is skipped unless `-f` is set.
- `description` defaults to an empty string if the `D` key is absent in the `info` file.
- The script walks the VDR source directory recursively – all recordings below
  the given path are processed.

---

## Output Example

```
============================================================
  tvh_addfile_vdr.py  v0.7
============================================================
  VDR source   : /mnt/fstab_virtiofs_tvh-storage/00_vdr
  TVH target   : /mnt/fstab_virtiofs_tvh-storage/recordings
  TVH API      : http://127.0.0.1:9981
  TVH user     : test
  Processing   : copy
  Force        : False
  Dry run      : False
============================================================

  Title   : Die Europa-Saga (2/6) | Woran wir glauben - Was wir denken
  Channel : 3sat  |  Start: 2025-05-07 14:50
  Source  : /mnt/fstab_virtiofs_tvh-storage/00_vdr/Die Europa-Saga/2025-05-07.14.50.00.rec/00001.ts
  Target  : /mnt/fstab_virtiofs_tvh-storage/recordings/Die Europa-Saga (2-6)2025-05-0714-50.ts
  + Kopiert
  + TVheadend registriert: a1b2c3d4-e5f6-7890-abcd-ef1234567890

============================================================
  Gesamt: 4  |  OK: 4  |  Uebersprungen: 0  |  Fehler: 0
============================================================
```

---

## License

(CC) BY-NC-SA – Speefak
