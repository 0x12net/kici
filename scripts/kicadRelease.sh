#!/bin/sh

# Production files generator.
# Usage: PRJ_VERSION=v0.0.0 PRJ_REPO=test ./kicadRelease.sh -s -p -g -c -a -b -i -l
#   -s sch pdf   -p pcb pdf   -d step      -g gerber+drill  -c cpl csv
#   -a asm pdf   -b bom csv   -i interactive bom            -l legend pdf
# Optional env: CORRECTIONCPLURL - url of a global cpl correction table (jlc)

PRJ_VERSION=${PRJ_VERSION:-"v0.0.0-def"}
PRJ_REPO=${PRJ_REPO:-"repo"}
KIPRJ_DIR_ARRAY=${KIPRJ_DIR_ARRAY:-"hardware*"}

KIPRJ_NAME=${KIPRJ_NAME:-"main"}
OUTPUT_DIR=${OUTPUT_DIR:-"build"}

mkdir -p $OUTPUT_DIR
OUTPUT_DIR=`realpath $OUTPUT_DIR`

if [ -n "$CORRECTIONCPLURL" ]; then
  wget -O ${OUTPUT_DIR}/correction_cpl_jlc.csv "$CORRECTIONCPLURL"
  awk 'NR==1 {print $1}' ${OUTPUT_DIR}/correction_cpl_jlc.csv | grep -q "Designator" && echo "INFO: File 'correction_cpl_jlc.csv' consistent" || (echo "ERROR: File 'correction_cpl_jlc.csv' is broken"; rm ${OUTPUT_DIR}/correction_cpl_jlc.csv;)
fi
  
for KIPRJ_DIR in $KIPRJ_DIR_ARRAY; do
  python3 /tools/prjVersion.py S ${PRJ_VERSION} ${KIPRJ_DIR};
done

while getopts 'spdgcabil' OPTION; do  
  for KIPRJ_DIR in $KIPRJ_DIR_ARRAY; do
    NAME=${PRJ_REPO}_${KIPRJ_DIR}_${PRJ_VERSION}
    TARGET_DIR=`realpath ${KIPRJ_DIR}`
    if [ ! -f "${TARGET_DIR}/${KIPRJ_NAME}.kicad_pro" ]; then
      echo "WARN: Skip folder ${TARGET_DIR}";
      continue;
    fi;
    case "$OPTION" in
      s)
        ## SCH
        echo "------------------- SCH [PDF] ------------------- "
        kicad-cli sch export pdf ${TARGET_DIR}/${KIPRJ_NAME}.kicad_sch -o ${OUTPUT_DIR}/${NAME}_sch.pdf -n
        ;;
      p)
        ## PCB
        echo "------------------- PCB [PDF] ------------------- "
        kicad-cli pcb export pdf ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb \
        						 -l 'F.Paste,F.Cu,F.Silkscreen,F.Courtyard,Edge.Cuts' --ibt --ev --drill-shape-opt 2 -o ${OUTPUT_DIR}/${NAME}_pcb_t.pdf 
        kicad-cli pcb export pdf ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb \
        						 -l 'B.Paste,B.Cu,B.Silkscreen,B.Courtyard,Edge.Cuts' -m --ibt --ev --drill-shape-opt 2 -o ${OUTPUT_DIR}/${NAME}_pcb_b.pdf 
        ;;
      d)
        ## 3D
        echo "------------------- 3D [STEP] ------------------- "
        kicad-cli pcb export step  ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/${NAME}.step \
        						   --grid-origin --no-dnp --subst-models --include-silkscreen --include-soldermask
        ;;
      g)
        ## GBR
        echo "-------------------- GBR+DRL -------------------- "
        mkdir -p ${OUTPUT_DIR}/gerber
        kicad-cli pcb export gerbers ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/gerber/ \
        							 --no-protel-ext \
        							 --ev \
        							 --use-drill-file-origin
        kicad-cli pcb export drill   ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/gerber/ \
        						     --format excellon --excellon-zeros-format decimal \
        						     --excellon-oval-format alternate -u mm --generate-map --map-format gerberx2 \
        						     --drill-origin plot
        cd ${OUTPUT_DIR}/gerber/
        # rename ${KIPRJ_NAME}-<Layer>.gbr to [<NN>_]${NAME}_<Layer>.gbr (NN keeps fab stack order)
        mvopt() { [ -f "${KIPRJ_NAME}-$1.gbr" ] && mv "${KIPRJ_NAME}-$1.gbr" "${2:+${2}_}${NAME}_$(echo "$1" | tr '_' '-').gbr"; }
        mvopt User_1 11
        mvopt User_2 12
        mvopt User_3 13
        mvopt User_4 14
        mvopt User_5 15
        mvopt F_Paste 20
        mvopt F_Silkscreen 21
        mvopt F_Mask 22
        mvopt F_Cu 25
        mvopt In1_Cu 26
        mvopt In2_Cu 27
        mvopt In3_Cu 28
        mvopt In4_Cu 29
        mvopt In5_Cu 30
        mvopt In6_Cu 31
        mvopt B_Cu 56
        mvopt B_Mask 60
        mvopt B_Silkscreen 61
        mvopt B_Paste 62
        mvopt Edge_Cuts 95
        mvopt User_6 96
        mvopt User_7 97
        mvopt User_8 98
        mvopt User_9 99
        mvopt User_Comments
        mvopt User_Drawings
        mv ${KIPRJ_NAME}.drl ${NAME}.drl
        mv ${KIPRJ_NAME}-drl_map.gbr ${NAME}_drl-map.gbr
        mv ${KIPRJ_NAME}-job.gbrjob ${NAME}_job.gbrjob
        rm -f ${KIPRJ_NAME}-*.gbr
        
        zip -r ${OUTPUT_DIR}/${NAME}.zip *
        rm -f *job.gbrjob *drl-map.gbr *User-Comments.gbr *User-Drawings.gbr
        zip -r ${OUTPUT_DIR}/${NAME}_rezonit.zip *
        cd -
        rm -rf ${OUTPUT_DIR}/gerber
        ;;
      c)
        ## CPL
        echo "------------------- CPL [CSV] ------------------- "
        kicad-cli pcb export pos   ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/${NAME}_cpl.csv \
        						   --side both --format csv --units mm --use-drill-file-origin
        sed -i 's/Ref/Designator/' ${OUTPUT_DIR}/${NAME}_cpl.csv
        sed -i 's/PosX/Mid X/'     ${OUTPUT_DIR}/${NAME}_cpl.csv
        sed -i 's/PosY/Mid Y/'     ${OUTPUT_DIR}/${NAME}_cpl.csv
        sed -i 's/Rot,/Rotation,/' ${OUTPUT_DIR}/${NAME}_cpl.csv
        sed -i 's/Side/Layer/'     ${OUTPUT_DIR}/${NAME}_cpl.csv


        echo "Designator,Package,Mid X,Mid Y,Rotation" > ${OUTPUT_DIR}/correction_cpl_${NAME}.csv
        if [ -f "${OUTPUT_DIR}/correction_cpl_jlc.csv" ]; then
          echo "INFO: Found ${OUTPUT_DIR}/correction_cpl_jlc.csv";\
          tail -n +2 ${OUTPUT_DIR}/correction_cpl_jlc.csv >> ${OUTPUT_DIR}/correction_cpl_${NAME}.csv; \
        fi;
        if [ -f "${TARGET_DIR}/correction_cpl_local.csv" ]; then
          echo "INFO: Found ${TARGET_DIR}/correction_cpl_local.csv";\
          tail -n +2 ${TARGET_DIR}/correction_cpl_local.csv >> ${OUTPUT_DIR}/correction_cpl_${NAME}.csv; \
        fi;
        sed -i '/^$/d' ${OUTPUT_DIR}/correction_cpl_${NAME}.csv;
        
        python3 /tools/cplCorrector.py "${OUTPUT_DIR}/${NAME}_cpl.csv" "${OUTPUT_DIR}/correction_cpl_${NAME}.csv" -o "${OUTPUT_DIR}/${NAME}_cpl_fix.csv"

        rm -f ${OUTPUT_DIR}/correction_cpl_${NAME}.csv
        ;;
      a)
        ## ASM
        echo "------------------- ASM [PDF] ------------------- "
        kicad-cli pcb export pdf ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/${NAME}_asm_t.pdf \
        						 -l 'F.Fab,Edge.Cuts' --cl 'User.Drawings' --cdnp --ev --ibt --black-and-white --drill-shape-opt 0
        kicad-cli pcb export pdf ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/${NAME}_asm_b.pdf \
        						 -l 'B.Fab,Edge.Cuts' --cl 'User.Drawings' --cdnp --ev --ibt --black-and-white --drill-shape-opt 0 -m
        ;;
      b)
        ## BOM
        echo "------------------- BOM [CSV] ------------------- "
        kicad-cli sch export bom ${TARGET_DIR}/${KIPRJ_NAME}.kicad_sch -o ${OUTPUT_DIR}/${NAME}_bom.csv \
         						 --preset general --format-preset CSV
        sed -i 's/"Value"/Comment/'         ${OUTPUT_DIR}/${NAME}_bom.csv
        sed -i 's/"Reference"/Designator/'  ${OUTPUT_DIR}/${NAME}_bom.csv
        # sed -i 's/"lcsc"/LCSC/'             ${OUTPUT_DIR}/${NAME}_bom.csv
        ;;
      i)
        echo "------------------ IBOM [HTML] ------------------ "
        echo "warning: ignored ibom.config.ini"
        # mv main-ibom.html  ${NAME}_ibom.html
        INTERACTIVE_HTML_BOM_NO_DISPLAY=true generate_interactive_bom.py ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb \
        --highlight-pin1 selected \
        --checkboxes Sourced,Placed \
        --bom-view left-right \
        --layer-view F \
        --no-browser \
        --dest-dir ${OUTPUT_DIR} \
        --name-format ${NAME} \
        --sort-order C,R,L,D,U,Y,X,F,SW,A,~,HS,CNN,J,P,NT,MH \
        --extra-data-file ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb \
        --show-fields mpn,Value,Coefficient,Voltage,Footprint \
        --group-fields Value,Coefficient,Voltage,Footprint 
        ;;
      l)
        ## Legend
        echo "------------------- Legend [PDF] ---------------- "
        kicad-cli pcb export pdf ${TARGET_DIR}/${KIPRJ_NAME}.kicad_pcb -o ${OUTPUT_DIR}/${NAME}_legend \
        						 -l 'User.Comments,User.Drawings,User.1,User.2,User.3,User.4,User.5,User.6,User.7,User.8,User.9' --cl 'Edge.Cuts' --ibt --drill-shape-opt 0 --mode-multipage
        if [ -d ${OUTPUT_DIR}/${NAME}_legend ]; then
          mv ${OUTPUT_DIR}/${NAME}_legend/${KIPRJ_NAME}.pdf ${OUTPUT_DIR}/${NAME}_legend.pdf
          rmdir ${OUTPUT_DIR}/${NAME}_legend
        else
          # kicad-cli writes a single file directly (no subdirectory) when only one page is produced
          mv ${OUTPUT_DIR}/${NAME}_legend ${OUTPUT_DIR}/${NAME}_legend.pdf
        fi
        ;;
      ?)
        echo "script usage: [PRJ_VERSION=vV.V.V-VVV] [PRJ_REPO=repo] [KIPRJ_DIR_ARRAY='hardware*'] [KIPRJ_NAME=main] [OUTPUT_DIR=build] $(basename $0) [-s][-p][-d][-g][-c][-a][-b][-i][-l]" >&2
        exit 1
        ;;
    esac
  done
done

for KIPRJ_DIR in $KIPRJ_DIR_ARRAY; do
  python3 /tools/prjVersion.py R ${PRJ_VERSION} ${KIPRJ_DIR};
done

rm -f ${OUTPUT_DIR}/correction_cpl_jlc.csv

shift "$(($OPTIND -1))"
