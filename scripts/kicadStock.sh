#!/bin/bash

# BOMVERIFIERARG="-qty=1 -lcsc=sku -lcscRW=mpn -digikey=mpn -digikeyRW=sku" PREVCOLUMN="qty,mpn,lcsc,lcsc_sku,lcsc_consistent,lcsc_stock" ./kicadStock.sh
# schematics are edited only when BOMVERIFIERARG contains rewrite (-*RW=) flags

PRJ_VERSION=${PRJ_VERSION:-"v0.0.0-def"}
PRJ_REPO=${PRJ_REPO:-"repo"}
KIPRJ_DIR_ARRAY=${KIPRJ_DIR_ARRAY:-"hardware*"}

KIPRJ_NAME=${KIPRJ_NAME:-"main"}
OUTPUT_DIR=${OUTPUT_DIR:-"build"}

BOMVERIFIERARG=${BOMVERIFIERARG:-"-lcsc=sku -lcscRW=mpn"}
PREVCOLUMN=${PREVCOLUMN:-"qty,mpn,lcsc,lcsc_sku,lcsc_consistent,lcsc_stock"}

# search:change property pairs written back to schematics via schPropEdit.
# Derived from the BOMVERIFIERARG rewrite flags unless set explicitly:
# -<provider>RW=mpn searches symbols by the <provider> property and rewrites mpn,
# -<provider>RW=sku searches symbols by mpn and rewrites the <provider> property
if [ -z "$SCHPROPEDIT_PAIRS" ]; then
  for ARG in $BOMVERIFIERARG; do
    case "$ARG" in
      -*RW=mpn) PROVIDER=${ARG#-}; SCHPROPEDIT_PAIRS="${SCHPROPEDIT_PAIRS} ${PROVIDER%RW=*}:mpn";;
      -*RW=sku) PROVIDER=${ARG#-}; SCHPROPEDIT_PAIRS="${SCHPROPEDIT_PAIRS} mpn:${PROVIDER%RW=*}";;
    esac
  done
fi

# USERAGENTURL=

if [ -n "$USERAGENTURL" ]; then
  export USERAGENT=`wget -q -O - ${USERAGENTURL}`
  echo "INFO: User-Agent:$USERAGENT"
fi

mkdir -p $OUTPUT_DIR
OUTPUT_DIR=`realpath $OUTPUT_DIR`

for KIPRJ_DIR in $KIPRJ_DIR_ARRAY; do

  NAME=${PRJ_REPO}_${KIPRJ_DIR}_${PRJ_VERSION}
  TARGET_DIR=`realpath ${KIPRJ_DIR}`
  if [ ! -f "${TARGET_DIR}/${KIPRJ_NAME}.kicad_pro" ]; then
    echo "WARN: Skip folder ${TARGET_DIR}";
    continue;
  fi;
  
  ## BOM
  kicad-cli sch export bom ${TARGET_DIR}/${KIPRJ_NAME}.kicad_sch -o ${OUTPUT_DIR}/${NAME}_bom.csv \
   						 --preset general --format-preset CSV
  sed -i 's/"Value"/Comment/'         ${OUTPUT_DIR}/${NAME}_bom.csv
  sed -i 's/"Reference"/Designator/'  ${OUTPUT_DIR}/${NAME}_bom.csv
  # sed -i 's/"lcsc"/LCSC/'             ${OUTPUT_DIR}/${NAME}_bom.csv

  python3 /tools/bomVerifier.py ${OUTPUT_DIR}/${NAME}_bom.csv -o ${OUTPUT_DIR}/${NAME}_bom_stock.csv ${BOMVERIFIERARG}

  if [ -n "$PREVCOLUMN" ]; then
    python3 /tools/csvExtractor.py ${OUTPUT_DIR}/${NAME}_bom_stock.csv \
    $PREVCOLUMN  \
    | sed "s/\",\"/;/g" | sed 's/^"//' | sed 's/"$//' | sed "s/_consistent/_ok/g"| LANG=C sed "s/[\x80-\xFF]/#/g" | column -t -s ";" -R 2 -o ' | ' \
    | sed "s/True/✅  /g" | sed "s/False/❌   /g";
  fi

  # for each SEARCH:CHANGE pair, symbols matched by property SEARCH get property CHANGE
  # set to the value from the same bom_stock csv row (columns are read by name)
  for SCH_FILE in ${TARGET_DIR}/*.kicad_sch; do
    for PAIR in $SCHPROPEDIT_PAIRS; do
      echo "schPropEdit - map ${PAIR%%:*} -> ${PAIR##*:} from ${NAME}_bom_stock.csv in $SCH_FILE"
      python3 /tools/schPropEdit.py ${SCH_FILE} --csv ${OUTPUT_DIR}/${NAME}_bom_stock.csv \
                                    --search_name "${PAIR%%:*}" --change_name "${PAIR##*:}"
    done
  done
done
