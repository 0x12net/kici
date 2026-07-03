#!/bin/sh

# Project consistency check.
# Usage: ./kicadRulesCheck.sh [-e][-d]
#   -e ERC   -d DRC

# KIPRJ_DIR is the legacy name of KIPRJ_DIR_ARRAY, kept for existing pipelines
KIPRJ_DIR_ARRAY=${KIPRJ_DIR_ARRAY:-${KIPRJ_DIR:-"hardware*"}}
KIPRJ_NAME=${KIPRJ_NAME:-"main"}
RETURNCODE=0

while getopts 'ed' OPTION; do
  for KIPRJ_DIR in $KIPRJ_DIR_ARRAY; do
    if [ ! -f "${KIPRJ_DIR}/${KIPRJ_NAME}.kicad_pro" ]; then
      echo "WARN: Skip folder ${KIPRJ_DIR}";
      continue;
    fi;
    case "$OPTION" in
      e)
        echo "Checking (ERC): ${KIPRJ_DIR}"
        kicad-cli sch erc --severity-error --exit-code-violations ${KIPRJ_DIR}/${KIPRJ_NAME}.kicad_sch -o ${KIPRJ_DIR}/${KIPRJ_NAME}-erc.rpt || RETURNCODE=1
        cat ${KIPRJ_DIR}/${KIPRJ_NAME}-erc.rpt
        rm ${KIPRJ_DIR}/${KIPRJ_NAME}-erc.rpt
        ;;
      d)
        echo "Checking (DRC): ${KIPRJ_DIR}"
        kicad-cli pcb drc --schematic-parity --severity-error --exit-code-violations ${KIPRJ_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${KIPRJ_DIR}/${KIPRJ_NAME}-drc.rpt || RETURNCODE=1
        cat ${KIPRJ_DIR}/${KIPRJ_NAME}-drc.rpt
        rm ${KIPRJ_DIR}/${KIPRJ_NAME}-drc.rpt
        ;;
    esac
  done
done
shift "$(($OPTIND -1))"

exit $RETURNCODE
