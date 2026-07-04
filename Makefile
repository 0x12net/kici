# ---------------------------------------------------------------------------
# Full pipeline smoke tests — build the real Dockerfile and drive the three
# scripts (kicadRulesCheck.sh / kicadStock.sh / kicadRelease.sh) exactly like
# the GitHub Actions workflows do, against a real KiCad project.
#
# PROJECT_DIR is never mounted directly: each pipeline-* target first copies
# it into build/pipeline/project (PROJECT_DIR is a sibling checkout, likely
# with its own uncommitted work) — kicadRelease.sh temporarily rewrites the
# version placeholder in-place and only restores it if the whole script
# reaches the end, so anything mounted read-write could be left modified by
# a failed run. Working on a throwaway copy means PROJECT_DIR is never at risk.
# ---------------------------------------------------------------------------

# Local credentials for pipeline-stock (DigiKey / Promelec), loaded from a
# gitignored .env if present — copy .env.example to .env to get started.
-include .env
export DIGIKEY_CLIENT_ID DIGIKEY_CLIENT_SECRET PROMELEC_LOGIN PROMELEC_PASSWORD

IMAGE          ?= kici:local
DOCKER_USER    ?= $(shell id -u):$(shell id -g)
PROJECT_DIR    ?= ../test
PRJ_VERSION    ?= v0.0.0
PRJ_REPO       ?= $(notdir $(patsubst %/,%,$(abspath $(PROJECT_DIR))))
PIPELINE_OUT   := build/pipeline
PROJECT_COPY   := $(PIPELINE_OUT)/project

BOMVERIFIERARG ?= -lcsc=sku -lcscRW=mpn -digikey=mpn -chipdip=mpn -promelec=sku -qty=1
PREVCOLUMN     ?= qty,mpn,lcsc_stock,digikey_stock,chipdip_stock,promelec_stock
RELEASE_FLAGS  ?= -s -p -d -g -c -a -b -i -l
CORRECTIONCPLURL ?= https://raw.githubusercontent.com/0x12net/metadata/refs/heads/main/correction_cpl_jlc.csv

define MODELS3D_REPOS_DEFAULT
KICAD8_3DMODEL_DIR=https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master
KICAD9_3DMODEL_DIR=https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master
KICAD10_3DMODEL_DIR=https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master
endef
MODELS3D_REPOS ?= $(MODELS3D_REPOS_DEFAULT)
export MODELS3D_REPOS

.PHONY: docker-build project-copy pipeline-rules pipeline-stock pipeline-release pipeline clean

docker-build:
	docker build -t $(IMAGE) .

project-copy:
	@test -d "$(PROJECT_DIR)/hardware" || \
		{ echo "No hardware/ project under PROJECT_DIR=$(PROJECT_DIR) -- override PROJECT_DIR=/path/to/kicad-repo"; exit 1; }
	rm -rf $(PROJECT_COPY)
	mkdir -p $(dir $(PROJECT_COPY))
	cp -a $(PROJECT_DIR) $(PROJECT_COPY)

pipeline-rules: docker-build project-copy
	docker run --rm --user "$(DOCKER_USER)" -v "$(abspath $(PROJECT_COPY)):/work" -w /work \
		$(IMAGE) kicadRulesCheck.sh -e -d

pipeline-stock: docker-build project-copy
	@mkdir -p $(PIPELINE_OUT)/stock
	docker run --rm --user "$(DOCKER_USER)" -v "$(abspath $(PROJECT_COPY)):/work" -w /work \
		-v "$(abspath $(PIPELINE_OUT))/stock:/output" -e OUTPUT_DIR=/output \
		-e PRJ_REPO=$(PRJ_REPO) -e PRJ_VERSION=$(PRJ_VERSION) \
		-e BOMVERIFIERARG="$(BOMVERIFIERARG)" -e PREVCOLUMN="$(PREVCOLUMN)" \
		-e DIGIKEY_CLIENT_ID -e DIGIKEY_CLIENT_SECRET \
		-e PROMELEC_LOGIN -e PROMELEC_PASSWORD \
		$(IMAGE) kicadStock.sh
	@echo "output: $(PIPELINE_OUT)/stock"

pipeline-release: docker-build project-copy
	@mkdir -p $(PIPELINE_OUT)/release
	docker run --rm --user "$(DOCKER_USER)" -v "$(abspath $(PROJECT_COPY)):/work" -w /work \
		-v "$(abspath $(PIPELINE_OUT))/release:/output" -e OUTPUT_DIR=/output \
		-e PRJ_REPO=$(PRJ_REPO) -e PRJ_VERSION=$(PRJ_VERSION) \
		-e CORRECTIONCPLURL="$(CORRECTIONCPLURL)" -e MODELS3D_REPOS \
		$(IMAGE) kicadRelease.sh $(RELEASE_FLAGS)
	@echo "output: $(PIPELINE_OUT)/release"

pipeline: pipeline-rules pipeline-stock pipeline-release

clean:
	rm -rf build
