import re
import argparse
from pathlib import Path

VERSION_PLACEHOLDER = 'vV.V.V-VVV'

parser = argparse.ArgumentParser(description='Set or restore the version placeholder in kicad project files')
parser.add_argument('mode', choices=['S', 'R'], help='S - set version instead of placeholder, R - restore placeholder')
parser.add_argument('version', help='Version like v1.2.3[-suffix]')
parser.add_argument('directory', help='Directory with *.kicad_* files')
args = parser.parse_args()

if not re.match(r"^v[0-9]+[.][0-9]+[.][0-9]+", args.version):
    print("Invalid version record format")
    exit(1)

for filename in Path(args.directory).glob("*.kicad_*"):
    print(f"Processing '{filename}'")
    filedata = filename.read_text()
    if args.mode == 'S':
        filedata = filedata.replace(VERSION_PLACEHOLDER, args.version)
    else:
        filedata = filedata.replace(args.version, VERSION_PLACEHOLDER)
    filename.write_text(filedata)
