#!/bin/bash

# BOMVERIFIERARG="-qty=1 -lcsc=sku -lcscRW=mpn -promelec -elitan" PREVCOLUMN="qty,mpn,lcsc,lcsc_sku,lcsc_consistent,lcsc_stock,promelec_consistent,promelec_stock,elitan_consistent,elitan_enough" ./kicadStock.sh schPropEdit

PRJ_VERSION=${PRJ_VERSION:-"v0.0.0-def"}
PRJ_REPO=${PRJ_REPO:-"repo"}
KIPRJ_DIR_ARRAY=${KIPRJ_DIR_ARRAY:-"hardware*"}

KIPRJ_NAME=${KIPRJ_NAME:-"main"}
OUTPUT_DIR=${OUTPUT_DIR:-"build"}

BOMVERIFIERARG=${BOMVERIFIERARG:-"-lcsc=sku -lcscRW=mpn"}
PREVCOLUMN=${PREVCOLUMN:-"qty,mpn,lcsc,lcsc_sku,lcsc_consistent,lcsc_stock"}

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

  if [[ "$1" != "schPropEdit" ]]; then
     continue;
  fi

  # build a single replacement table (search_name,search_value,change_name,change_value)
  # so schPropEdit.py can apply every mpn:lcsc pair in one pass over each schematic file
  REPLACEMENTS_CSV=${OUTPUT_DIR}/${NAME}_replacements.csv
  echo "search_name,search_value,change_name,change_value" > ${REPLACEMENTS_CSV}
  python3 /tools/csvExtractor.py ${OUTPUT_DIR}/${NAME}_bom_stock.csv "lcsc,mpn" | sed "s/,/ /g" | while read line || [[ -n $line ]];
  do
    set -- $line;
    SEARCH_VALUE=`echo $1 | sed 's/^"//' | sed 's/"$//'`
    CHANGE_VALUE=`echo $2 | sed 's/^"//' | sed 's/"$//'`

    if [[ ! -n "$SEARCH_VALUE" || ! -n "$CHANGE_VALUE" || "$SEARCH_VALUE" = "lcsc" ]]; then
       # echo "skip row"
       continue;
    fi

    echo "lcsc,${SEARCH_VALUE},mpn,${CHANGE_VALUE}" >> ${REPLACEMENTS_CSV}
  done

  for SCH_FILE in ${TARGET_DIR}/*.kicad_sch; do
    echo "schPropEdit - apply $((`wc -l < ${REPLACEMENTS_CSV}` - 1)) replacements from ${REPLACEMENTS_CSV} in $SCH_FILE"
    python3 /tools/schPropEdit.py ${SCH_FILE} --csv ${REPLACEMENTS_CSV}
  done
done
