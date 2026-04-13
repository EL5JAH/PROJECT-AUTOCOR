# AUTOCOR Lab – Network Automation Foundation

## Overview

This repository provides a repeatable, automation-focused network lab aligned with Cisco automation exam objectives (DEVASC / ENAUTO / DEVCOR).

The goal is to:

- Rapidly deploy a working network topology (CML or DevNet)
- Validate baseline network health automatically
- Provide a foundation for building automation workflows (Python, RESTCONF, Ansible, etc.)
- Simulate real-world enterprise scenarios

## Key Features

- Fast lab deployment via base YAML
- Automated baseline validation
- Structured artifact/logging system
- Versioned lab evolution
- Designed for iterative automation development

## Repository Structure

repo/
├── artifacts/
│ └── runs/
├── lab/
│ └── base-lab.yaml
├── scripts/
│ └── baseline_validate.py
├── expected_state/
│ └── expected_state.yaml
├── docs/
│ └── conventions.md
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── VERSION
└── meta.txt

## Quick Start

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Run Validation

python scripts/baseline_validate.py

## Artifacts

artifacts/runs/<timestamp>/

## Versioning

MAJOR.MINOR.PATCH

## Philosophy

Build once. Validate always. Automate everything.

## Supported Environments

| Environment    | Lab Creation | Supported |
| -------------- | ------------ | --------- | ------------------------------------- |
| CML Licensed   | ✅           | Full      | Fully automated lab creation          |
| DevNet Sandbox | ❌           | Partial   | Manual YAML upload lab creation       |
| No CML         | ❌           | Limited   | Portable Network Automation Framework |
