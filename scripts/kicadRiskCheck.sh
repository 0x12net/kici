#!/bin/sh

# Parts risk check.
# Usage: RISKCLASSIFICATIONURL=<url|path> ./kicadRiskCheck.sh
# Fetches the risk classification table (columns: risk_level,part,description) --
# RISKCLASSIFICATIONURL may be an http(s) url or a local file path (e.g. a
# metadata checkout mounted into the container, for testing without a push) --
# and checks every BOM part (chip name or mpn/sku) against it. Exits non-zero
# if any project has a part reaching RISK_FAIL_LEVEL.

PRJ_VERSION=${PRJ_VERSION:-"v0.0.0-def"}
PRJ_REPO=${PRJ_REPO:-"repo"}
KIPRJ_DIR_ARRAY=${KIPRJ_DIR_ARRAY:-"hardware*"}
KIPRJ_NAME=${KIPRJ_NAME:-"main"}
OUTPUT_DIR=${OUTPUT_DIR:-"build"}
RISK_FAIL_LEVEL=${RISK_FAIL_LEVEL:-3}
RETURNCODE=0

if [ -z "$RISKCLASSIFICATIONURL" ]; then
  echo "CRITICAL: RISKCLASSIFICATIONURL is not set"
  exit 2
fi

mkdir -p $OUTPUT_DIR
OUTPUT_DIR=`realpath $OUTPUT_DIR`

case "$RISKCLASSIFICATIONURL" in
  http://*|https://*) wget -O ${OUTPUT_DIR}/risk_classification.csv "$RISKCLASSIFICATIONURL" ;;
  *) cp "$RISKCLASSIFICATIONURL" ${OUTPUT_DIR}/risk_classification.csv ;;
esac
awk 'NR==1 {print $1}' ${OUTPUT_DIR}/risk_classification.csv | grep -q "risk_level" \
  && echo "INFO: File 'risk_classification.csv' consistent" \
  || { echo "CRITICAL: File 'risk_classification.csv' is broken"; rm -f ${OUTPUT_DIR}/risk_classification.csv; exit 2; }

for KIPRJ_DIR in $KIPRJ_DIR_ARRAY; do
  NAME=${PRJ_REPO}_${KIPRJ_DIR}_${PRJ_VERSION}
  TARGET_DIR=`realpath ${KIPRJ_DIR}`
  if [ ! -f "${TARGET_DIR}/${KIPRJ_NAME}.kicad_pro" ]; then
    echo "WARN: Skip folder ${TARGET_DIR}";
    continue;
  fi;

  echo "------------------- RISK [${KIPRJ_DIR}] ------------------- "
  kicad-cli sch export bom ${TARGET_DIR}/${KIPRJ_NAME}.kicad_sch -o ${OUTPUT_DIR}/${NAME}_bom.csv \
                           --preset general --format-preset CSV
  sed -i 's/"Value"/Comment/'         ${OUTPUT_DIR}/${NAME}_bom.csv
  sed -i 's/"Reference"/Designator/'  ${OUTPUT_DIR}/${NAME}_bom.csv

  python3 /tools/riskChecker.py ${OUTPUT_DIR}/${NAME}_bom.csv ${OUTPUT_DIR}/risk_classification.csv \
    -o ${OUTPUT_DIR}/${NAME}_risk.csv --fail-level ${RISK_FAIL_LEVEL} || RETURNCODE=1
done

rm -f ${OUTPUT_DIR}/risk_classification.csv

exit $RETURNCODE
