# Network Automation Makefile

.PHONY: help install generate deploy server clean

help:
	@echo "Available commands:"
	@echo "  make install   - Install Python dependencies"
	@echo "  make generate  - Generate Cisco IOS configurations locally (no GNS3 deploy)"
	@echo "  make deploy    - Generate configurations and deploy topology directly to GNS3"
	@echo "  make server    - Run the GUI Web Server (port 8080)"
	@echo "  make clean     - Clean up generated configuration files"

install:
	pip install -r requirements.txt

generate:
	python3 main.py --no-deploy

deploy:
	python3 main.py

server:
	python3 server.py

clean:
	rm -f generated_configs/*.cfg
