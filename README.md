# kici

The repository contains the source code of the docker image. Designed to automate the development of electronic devices in kicad.

I do not guarantee the functionality and backward compatibility of the pipeline. I support it for my processes.

## Features

- `kicad-release` - System for generating production documentation
  
  - gerber + drill
  
  - bom + interactive bom
  
  - assembly drawing + board legend
  
  - schematic diagram
  
  - placement file with jlc corrections

- `kicad-rules-check` - Project consistency check
  
  - ERC
  
  - DRC

- `kicad-stock` - Parts Availability Check System
  
  - lcsc
  
  - digikey
  
  - Automatic `mpn` detection function by `sku` lcsc

- ISSUE_TEMPLATE


### Requirements:

- There should be no spaces in directory and file names. [See](https://github.com/Artel-Inc/faq/blob/main/general_naming_guid.md)

- The `kicad` project must be named `main` (Can be changed via env pipeline). [See](https://github.com/Artel-Inc/faq/blob/main/hardware_repository_structure.md)

- One repository can store several PCBs. The directory should be called hardware, hardware-test....

- The board version should be `vV.V.V-VVV`. [See](https://github.com/Artel-Inc/faq/blob/main/general_version_guid.md)

### Description of versioning

Notation: vA.B.C

Where:

- A - MAJOR version `kicad`

- B - MINOR version `kicad`

- C - Edition number `kici`

I recommend specifying the exact version of the docker image in the pipeline.

## Changelog:

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
