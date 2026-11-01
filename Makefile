SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE      ?= docker compose
PY           ?= $(shell command -v python3 2>/dev/null || command -v python)
SECRET_FILE  ?= docker/secrets/wargame_secret
LEVELS       ?= levels

export PYTHONPATH := engine
export WARGAME_SECRET_FILE ?= $(SECRET_FILE)

PLAYER ?= player00

.PHONY: help secret deps build up down restart logs ps shell bootstrap test check audit \
        stats validate validate-all validate-hardened new-level rotate rotate-epoch clean

help: ## Bu listeyi göster
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

secret: ## Yerel geliştirme sırrı üret (varsa dokunmaz)
	@test -s $(SECRET_FILE) || { mkdir -p docker/secrets; head -c 32 /dev/urandom | base64 > $(SECRET_FILE); chmod 600 $(SECRET_FILE); echo "üretildi: $(SECRET_FILE)"; }

deps: ## Geliştirme bağımlılıkları (venv önerilir)
	$(PY) -m pip install -e ./engine pytest

build: secret ## İmajı derle
	$(COMPOSE) build

up: secret ## Sandbox'ı başlat
	$(COMPOSE) up -d --wait
	@echo
	@echo "giriş:  ssh player00@$${WARGAME_HOSTNAME:-localhost} -p $${WARGAME_PORT:-2222}"
	@$(PY) -m wargame login 00

down: ## Durdur ve hacimleri sil
	$(COMPOSE) down -v --remove-orphans

restart: down up ## Sıfırdan başlat

logs: ## Konteyner günlükleri
	$(COMPOSE) logs -f --tail=100

ps: ## Durum
	$(COMPOSE) ps

shell: ## Konteynerde kabuk (PLAYER=player02)
	$(COMPOSE) exec -u $(PLAYER) sandbox bash

bootstrap: ## player00 giriş bilgisi
	@$(PY) -m wargame login 00

test: ## Birim testleri
	$(PY) -m pytest tests -q

check: ## Seviye tanımlarını doğrula
	$(PY) -m wargame check

audit: ## Çalışan sandbox'ta sızıntı denetimi
	$(COMPOSE) exec -T sandbox python3 -m wargame audit

stats: ## İlerleme defterini özetle (skor tablosu)
	$(COMPOSE) exec -T sandbox python3 -m wargame stats

validate: ## Tek seviyeyi çöz (LEVEL=01)
	@test -n "$(LEVEL)" || { echo "kullanım: make validate LEVEL=01"; exit 2; }
	bash scripts/validate-level.sh "$(LEVEL)"

validate-all: ## Tüm seviyeleri çöz (çözümler varsa)
	bash scripts/validate-all.sh

validate-hardened: ## Tüm seviyeleri sertleştirilmiş profilde çöz
	COMPOSE_FILE=deploy/container-compose.yaml bash scripts/validate-all.sh

new-level: ## Yeni seviye iskeleti (ID=03 TITLE="Başlık")
	@test -n "$(ID)" || { echo "kullanım: make new-level ID=03 TITLE=\"Başlık\""; exit 2; }
	bash scripts/new-level.sh "$(ID)" "$(TITLE)"

rotate: ## Yalnızca dönemi değiştir (EPOCH=2027Q1)
	@test -n "$(EPOCH)" || { echo "kullanım: make rotate EPOCH=2027Q1"; exit 2; }
	bash scripts/rotate-flags.sh "$(EPOCH)"

rotate-epoch: ## Yeni sır + yeni dönem + temiz konteyner (EPOCH=2027Q1)
	bash scripts/rotate-epoch.sh $(if $(EPOCH),$(EPOCH),)

clean: down ## İmajı ve hacimleri sil
	-$(COMPOSE) down -v --rmi local --remove-orphans
