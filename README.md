# kici

**Ki**Cad **CI** — a docker image for automating the development of electronic devices in [KiCad](https://www.kicad.org/): production files, ERC/DRC checks and parts availability directly in the pipeline.

```
ghcr.io/0x12net/kici:<tag>
```

> [!WARNING]
> I do not guarantee the functionality and backward compatibility of the pipeline. I support it for my processes.

## What's inside

Based on the official [`ghcr.io/kicad/kicad`](https://github.com/KiCad/kicad-cli-docker) image, with the addition of:

- [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom)
- [kdif](https://github.com/0x12net/kdif) — interactive HTML diff of a board/schematic between git revisions
- `/scripts` — pipeline entry points (available in `PATH`)
- `/tools` — python utilities used by the scripts, also usable standalone

## Scripts

Common environment variables:

| Variable | Default | Description |
|---|---|---|
| `PRJ_VERSION` | `v0.0.0-def` | Board version, replaces the `vV.V.V-VVV` placeholder in project files |
| `PRJ_REPO` | `repo` | Repository name, used in output file names |
| `KIPRJ_DIR_ARRAY` | `hardware*` | Glob of directories with KiCad projects |
| `KIPRJ_NAME` | `main` | KiCad project file name |
| `OUTPUT_DIR` | `build` | Output directory |

### kicadRelease.sh — production documentation

```sh
PRJ_VERSION=${GITHUB_REF_NAME} kicadRelease.sh -s -p -g -c -a -b -i -l
```

| Flag | Output |
|---|---|
| `-s` | Schematic diagram (pdf) |
| `-p` | Board top/bottom views (pdf) |
| `-d` | 3D model (step) |
| `-g` | Gerber + drill, zipped (generic + rezonit variant) |
| `-c` | Placement file (csv) with rotation/offset corrections |
| `-a` | Assembly drawings (pdf) |
| `-b` | BOM (csv) |
| `-i` | Interactive HTML BOM |
| `-l` | Board legend from `User.*` layers (pdf) |

Placement corrections (`-c`) are merged from two sources: a global table fetched from `CORRECTIONCPLURL` (`http(s)://` url or local file path) and a local `correction_cpl_local.csv` in the project directory. Both are applied by `cplCorrector.py`.

The 3D model (`-d`) is exported with `kicad-cli --subst-models`, which needs the footprints' 3D models available under the `${VAR}` variables referenced in the board file (e.g. `(model "${KICAD9_3DMODEL_DIR}/LED_THT.3dshapes/LED_D3.0mm.wrl" ...)`). The image does not bundle any 3D model library — `download3dModels.py` scans the board for the variables/paths it actually references and downloads only those files, from repos configured per variable in `MODELS3D_REPOS`:

```yaml
MODELS3D_REPOS: |
  KICAD8_3DMODEL_DIR=https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master
  KICAD9_3DMODEL_DIR=https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master
  KICAD10_3DMODEL_DIR=https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master
  MYCOMPANY_3DMODELS=https://raw.githubusercontent.com/myorg/my-3d-models/main
```

Each line maps one `${VAR}` to the raw base URL of a repository/folder with the matching `*.3dshapes` layout — any number of repos, on any host that serves raw files (GitLab, GitHub, ...), can be listed. If `MODELS3D_REPOS` is unset, `-d` runs kicad-cli as-is (no download step). Models that fail to download (no repo configured for their variable, or not found at that path) are printed as warnings and simply left out of the export instead of failing the build.


| Variable | Default | Description |
|---|---|---|
| `MODELS3D_REPOS` | — | `VAR=URL` lines (one per repo) used to resolve 3D model variables for `-d` |
| `MODELS3D_CACHE_DIR` | `/tmp/3dmodels_cache` | Local directory downloaded models are cached in |

### kicadRulesCheck.sh — project consistency check

```sh
kicadRulesCheck.sh -e   # ERC
kicadRulesCheck.sh -d   # DRC (with schematic parity)
```

Prints the violation report and exits non-zero if there are errors.

### kicadRiskCheck.sh — parts risk check

Exports the BOM and checks every non-empty BOM column of every part (chip name, mpn, distributor sku, or any other field) against a risk classification table (columns: `risk_level,part,description`; `part` accepts `*`/`?` wildcards, matched case-insensitively). Prints a report and exits non-zero if the highest risk level found reaches `RISK_FAIL_LEVEL`; lower levels are reported but the build still passes.

| Variable | Default | Description |
|---|---|---|
| `RISKCLASSIFICATIONURL` | — (required) | `http(s)://` url or local file path of the risk classification csv, e.g. hosted in [metadata](https://github.com/0x12net/metadata) (a local path is handy for testing an uncommitted table -- see `METADATA_DIR` in the [Makefile](Makefile)) |
| `RISK_FAIL_LEVEL` | `3` | Risk level (`1`/`2`/`3`) at which the pipeline fails |

### kicadStock.sh — parts availability check

Exports the BOM, queries distributors (`bomVerifier.py`) for stock, price and consistency, and prints a summary table.

Supported providers: `lcsc`, `digikey`, `chipdip`, `promelec`. `chipdip` and `promelec` have
no official partner API for third-party sku/price lookup, so they scrape/drive undocumented
endpoints instead (`chipdip.py`/`promelec.py`) — expect unversioned responses, anti-bot, and,
for `promelec`, a required PROM2PROM (`office.promelec.ru`) partner account.

| Variable | Default | Description |
|---|---|---|
| `BOMVERIFIERARG` | `-lcsc=sku -lcscRW=mpn` | Arguments passed to `bomVerifier.py`: `-<provider>=<field>` — search by field, `-<provider>RW=<field>` — rewrite field with found data, `-qty=N` — order quantity |
| `PREVCOLUMN` | `qty,mpn,lcsc,...` | Columns of the summary table printed to the log (empty = disable) |
| `SCHPROPEDIT_PAIRS` | derived | `search:change` property pairs written back into schematics; derived from the `-*RW=` flags of `BOMVERIFIERARG` unless set explicitly |
| `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET` | — | DigiKey API v4 credentials (2-legged OAuth, CI-friendly) |
| `DIGIKEY_CLIENT_SANDBOX` | `False` | Use the DigiKey sandbox host |
| `PROMELEC_LOGIN` / `PROMELEC_PASSWORD` | — | PROM2PROM (`office.promelec.ru`) partner account credentials, required by the `promelec` provider |
| `RUB_USD_RATE` | fetched from `cbr.ru` | Override the RUB→USD rate used to convert `chipdip`/`promelec` prices (both quote in RUB, all `*_price` columns are USD) |
| `USERAGENT` / `USERAGENTURL` | — | User-Agent string, or a url to fetch it from |
| `SOCKS5_URL` / `SOCKS5_USERNAME` / `SOCKS5_PASSWORD` | — | SOCKS5 proxy for API requests |

When `BOMVERIFIERARG` contains rewrite flags (`-*RW=`), the found `mpn`/`sku` values are automatically written back into the schematic properties via `schPropEdit.py`.

## Tools

| Tool | Purpose |
|---|---|
| `bomVerifier.py` | Enrich a BOM csv with distributor data (stock, price, consistency) |
| `riskChecker.py` | Check BOM parts (chip name / mpn / sku) against a risk classification table |
| `cplCorrector.py` | Apply rotation/offset corrections to a placement file |
| `schPropEdit.py` | Batch edit of symbol properties in `.kicad_sch` files |
| `csvExtractor.py` | Extract selected columns from a csv |
| `prjVersion.py` | Set/restore the version placeholder in project files |
| `download3dModels.py` | Download only the 3D models a board references, from per-variable repos (see `-d`/`MODELS3D_REPOS`) |

## Requirements for the hardware repository

- No spaces in directory and file names. [See](https://github.com/0x12net/handbook/blob/main/general_naming_guid.md)
- The KiCad project must be named `main` (can be changed via `KIPRJ_NAME`). [See](https://github.com/0x12net/handbook/blob/main/hardware_repository_structure.md)
- One repository can store several PCBs; directories should be called `hardware`, `hardware-test`, ...
- The board version placeholder should be `vV.V.V-VVV`. [See](https://github.com/0x12net/handbook/blob/main/general_version_guid.md)

## Versioning

Notation: `vA.B.C`

- `A` — MAJOR version of KiCad
- `B` — MINOR version of KiCad
- `C` — edition number of `kici`

I recommend pinning the exact version of the docker image in the pipeline.

## Changelog

### v10.0.3

- add kdif (interactive HTML diff of a board/schematic between git revisions)

### v10.0.2

- add kicadRiskCheck.sh / riskChecker.py (parts risk classification check)
- CORRECTIONCPLURL/RISKCLASSIFICATIONURL now also accept a local file path (not just http(s))

### v10.0.1

- update kicad
- add support digikey, chipdip, promelec
- del kicad-command
- refactoring

### v9.0.2

- Fix asm pdf

### v9.0.1

- Add PROPHIDE, PROPEDIT in kicad-command
- Add PROPEDIT in kicad-stock

### v9.0.0

- Init
