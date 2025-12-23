PACKAGE_DIR=src/nodereaper
DOCKER_IMAGE=ghcr.io/sdaberdaku/nodereaper:latest
HELM_CHART=helm

.PHONY: help
help:
	@echo "NodeReaper Makefile Commands"
	@echo ""
	@echo "Development:"
	@echo "  dev-setup          Set up development environment"
	@echo "  install            Install package in editable mode"
	@echo "  install-dev        Install development dependencies"
	@echo "  format             Format code with black and isort"
	@echo ""
	@echo "Testing:"
	@echo "  test               Run unit tests"
	@echo "  test-integration   Run integration tests with kind"
	@echo "  test-helm          Run Helm chart tests"
	@echo "  test-all           Run all tests"
	@echo "  checks             Run all quality checks"
	@echo ""
	@echo "Helm:"
	@echo "  helm-install       Install NodeReaper with Helm"
	@echo "  helm-install-prod  Install with production values"
	@echo "  helm-uninstall     Uninstall Helm release"
	@echo "  helm-lint          Lint Helm chart"
	@echo "  helm-package       Package Helm chart"
	@echo ""
	@echo "Cluster:"
	@echo "  setup-cluster      Set up kind test cluster"
	@echo "  cleanup            Clean up everything"
	@echo "  logs               Show NodeReaper logs"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build       Build Docker image"
	@echo "  docker-build-multiarch  Build multi-arch image"

.PHONY: install
install:
	pip install -e .

.PHONY: install-dev
install-dev:
	scripts/setup-dev.sh

.PHONY: pre-commit-install
pre-commit-install:
	pre-commit install --install-hooks

.PHONY: pre-commit-run
pre-commit-run:
	pre-commit run --all-files

.PHONY: pre-commit-update
pre-commit-update:
	pre-commit autoupdate

# Testing targets
.PHONY: test
test:
	pytest tests/ -v -m "not integration"

.PHONY: test-cov
test-cov:
	pytest tests/ -v --cov=$(PACKAGE_DIR) --cov-report=html --cov-report=term-missing -m "not integration"

.PHONY: test-integration
test-integration:
	scripts/run-integration-tests.sh

.PHONY: test-helm
test-helm:
	scripts/test-helm-chart.sh

.PHONY: test-all
test-all: test test-integration test-helm
	@echo "🎉 All tests completed successfully!"

# Quality checks
.PHONY: lint
lint:
	black --check src/nodereaper/*.py
	isort --check-only src/nodereaper/*.py

.PHONY: format
format:
	black src/nodereaper/*.py
	isort src/nodereaper/*.py

.PHONY: checks
checks: lint test helm-lint helm-template pre-commit-run
	@echo "🎉 All quality checks passed!"

.PHONY: docker-build
docker-build:
	docker build -t $(DOCKER_IMAGE) .

.PHONY: docker-build-multiarch
docker-build-multiarch:
	docker buildx create --use --name multiarch-builder || true
	docker buildx build --platform linux/amd64,linux/arm64 -t $(DOCKER_IMAGE) --push .

# Helm operations
.PHONY: helm-lint
helm-lint:
	helm lint $(HELM_CHART)

.PHONY: helm-template
helm-template:
	helm template nodereaper $(HELM_CHART) --debug

.PHONY: helm-install
helm-install:
	helm upgrade --install nodereaper $(HELM_CHART) --namespace nodereaper --create-namespace

.PHONY: helm-install-prod
helm-install-prod:
	helm upgrade --install nodereaper $(HELM_CHART) \
		--namespace nodereaper --create-namespace \
		--set config.dryRun=false \
		--set config.enableFinalizerCleanup=true \
		--set config.finalizerTimeout=10m

.PHONY: helm-uninstall
helm-uninstall:
	scripts/cleanup.sh --helm-only

.PHONY: helm-package
helm-package:
	helm package $(HELM_CHART)

# Utilities
.PHONY: logs
logs:
	kubectl logs -n nodereaper -l app.kubernetes.io/name=nodereaper --tail=50

.PHONY: run-local
run-local:
	nodereaper

# Version management
.PHONY: version-check
version-check:
	scripts/check-version.sh

.PHONY: release
release:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make release VERSION=1.2.0"; \
		exit 1; \
	fi
	scripts/prepare-release.sh $(VERSION)

# Cluster management
.PHONY: setup-cluster
setup-cluster:
	scripts/setup-test-cluster.sh

.PHONY: cleanup
cleanup:
	scripts/cleanup.sh --all
# Development workflow
.PHONY: dev-setup
dev-setup: install-dev
	@echo "🚀 Development environment ready!"
	@echo "💡 Run 'make help' to see all available commands"
