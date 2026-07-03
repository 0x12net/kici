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

Placement corrections (`-c`) are merged from two sources: a global table fetched from `CORRECTIONCPLURL` and a local `correction_cpl_local.csv` in the project directory. Both are applied by [cplCorrector.py](docs/system_requirements_cplСorrector.md).

### kicadRulesCheck.sh — project consistency check

```sh
kicadRulesCheck.sh -e   # ERC
kicadRulesCheck.sh -d   # DRC (with schematic parity)
```

Prints the violation report and exits non-zero if there are errors.

### kicadStock.sh — parts availability check

Exports the BOM, queries distributors ([bomVerifier.py](docs/system_requirements_bomVerifier.md)) for stock, price and consistency, and prints a summary table.

Supported providers: `lcsc`, `digikey`.

| Variable | Default | Description |
|---|---|---|
| `BOMVERIFIERARG` | `-lcsc=sku -lcscRW=mpn` | Arguments passed to `bomVerifier.py`: `-<provider>=<field>` — search by field, `-<provider>RW=<field>` — rewrite field with found data, `-qty=N` — order quantity |
| `PREVCOLUMN` | `qty,mpn,lcsc,...` | Columns of the summary table printed to the log (empty = disable) |
| `SCHPROPEDIT_PAIRS` | derived | `search:change` property pairs written back into schematics; derived from the `-*RW=` flags of `BOMVERIFIERARG` unless set explicitly |
| `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET` | — | DigiKey API v4 credentials (2-legged OAuth, CI-friendly) |
| `DIGIKEY_CLIENT_SANDBOX` | `False` | Use the DigiKey sandbox host |
| `USERAGENT` / `USERAGENTURL` | — | User-Agent string, or a url to fetch it from |
| `SOCKS5_URL` / `SOCKS5_USERNAME` / `SOCKS5_PASSWORD` | — | SOCKS5 proxy for API requests |

When `BOMVERIFIERARG` contains rewrite flags (`-*RW=`), the found `mpn`/`sku` values are automatically written back into the schematic properties via [schPropEdit.py](docs/system_requirements_schPropEdit.md).

## Tools

| Tool | Purpose |
|---|---|
| [bomVerifier.py](docs/system_requirements_bomVerifier.md) | Enrich a BOM csv with distributor data (stock, price, consistency) |
| [cplCorrector.py](docs/system_requirements_cplСorrector.md) | Apply rotation/offset corrections to a placement file |
| [schPropEdit.py](docs/system_requirements_schPropEdit.md) | Batch edit of symbol properties in `.kicad_sch` files |
| `csvExtractor.py` | Extract selected columns from a csv |
| `prjVersion.py` | Set/restore the version placeholder in project files |

## Requirements for the hardware repository

- No spaces in directory and file names. [See](https://github.com/Artel-Inc/faq/blob/main/general_naming_guid.md)
- The KiCad project must be named `main` (can be changed via `KIPRJ_NAME`). [See](https://github.com/Artel-Inc/faq/blob/main/hardware_repository_structure.md)
- One repository can store several PCBs; directories should be called `hardware`, `hardware-test`, ...
- The board version placeholder should be `vV.V.V-VVV`. [See](https://github.com/Artel-Inc/faq/blob/main/general_version_guid.md)

## Versioning

Notation: `vA.B.C`

- `A` — MAJOR version of KiCad
- `B` — MINOR version of KiCad
- `C` — edition number of `kici`

I recommend pinning the exact version of the docker image in the pipeline.

## Changelog

### v10.0.2

- kicad-stock: automatic write-back of found `mpn`/`sku` into schematic properties (`SCHPROPEDIT_PAIRS`)
- schPropEdit: batch replacement (`--csv`) and column-mapping modes
- digikey: 2-legged OAuth (client credentials), price fallback below MOQ
- refactoring: unified exceptions in bomverifier, `KIPRJ_NAME` support in gerber renaming

### v10.0.1

- update kicad
- add support digikey
- del kicad-command

### v9.0.2

- Fix asm pdf

### v9.0.1

- Add PROPHIDE, PROPEDIT in kicad-command
- Add PROPEDIT in kicad-stock

### v9.0.0

- Init
