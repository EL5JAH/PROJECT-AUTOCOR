# PROJECT-AUTOCOR Architecture Guide

## Overview

PROJECT-AUTOCOR is a portable infrastructure automation platform built to support:

- Cisco DevNet learning
- CCNP Automation (AUTOCOR)
- Infrastructure automation development
- Configuration management
- Validation and compliance testing
- CI/CD experimentation
- Network operations workflows

The project is intentionally designed to separate:

- Lab infrastructure
- Automation tooling
- Validation tooling
- Test frameworks
- Development workflows

This separation allows the platform to grow without requiring major architectural changes.

---

# Design Goals

The platform was built around several core principles:

## Reproducibility

A new automation host should be capable of rebuilding the entire environment from source control.

## Portability

The lab should be deployable in:

- Cisco Modeling Labs (CML)
- VMware
- Physical hardware
- Cloud-hosted Linux systems

## Isolation

Automation tooling should not contaminate the underlying operating system.

Examples:

- Python uses virtual environments
- pyATS runs in Docker
- Secrets remain outside Git

## Auditability

Every automation run should generate artifacts that can be reviewed later.

## Extensibility

Future technologies should integrate cleanly:

- Terraform
- FastMCP
- GitLab CI/CD
- RESTCONF
- NETCONF
- Telemetry
- Compliance testing

---

# High-Level Architecture

```text
                        GitHub / GitLab
                               |
                               |
                               v

                    +----------------------+
                    |   Automation Host    |
                    |----------------------|
                    | Ubuntu Server        |
                    | Python Virtual Env   |
                    | Ansible              |
                    | Docker               |
                    | pyATS Runtime        |
                    +----------+-----------+
                               |
                               |
             -------------------------------------
             |                 |                 |
             |                 |                 |
             v                 v                 v

       +-----------+    +-----------+    +-----------+
       | IOS-XE    |    | IOS-XE    |    | IOS-XE    |
       | Device    |    | Device    |    | Device    |
       +-----------+    +-----------+    +-----------+
```

---

# Lab Topology

The primary lab topology is built within Cisco Modeling Labs.

## Infrastructure Devices

### CAT8K-1

Role:

- WAN edge router
- Internet access
- OSPF participant

Loopback:

```text
1.1.1.1/32
```

---

### CAT8K-2

Role:

- Primary internal router
- VLAN gateway
- OSPF participant
- NAT services

Loopback:

```text
2.2.2.2/32
```

Provides:

```text
VLAN 10
VLAN 20
VLAN 30
VLAN 99
```

---

### CAT8K-3

Role:

- Additional WAN/transit node
- Future automation target
- Routing experimentation

---

### CAT9K

Role:

- Core routing platform
- OSPF redistribution testing
- Layer-3 aggregation

Loopback:

```text
3.3.3.3/32
```

---

### Distribution Switches

Originally:

```text
DIST-SW1
DIST-SW2
```

Later migrated toward IOSv Layer-3 switches for additional flexibility.

Responsibilities:

- Access VLANs
- Routing experimentation
- Ansible testing targets

---

# VLAN Architecture

## User VLANs

### VLAN 10

```text
10.10.10.0/24
Gateway: 10.10.10.1
```

---

### VLAN 20

```text
10.20.20.0/24
Gateway: 10.20.20.1
```

---

### VLAN 30

```text
10.30.30.0/24
Gateway: 10.30.30.1
```

---

## Management VLAN

### VLAN 99

```text
10.99.99.0/24
```

Management devices:

```text
CAT8K-2     10.99.99.1
DIST-SW1    10.99.99.11
DIST-SW2    10.99.99.12
AUTO-HOST   10.99.99.50
```

Purpose:

- SSH management
- Automation access
- Ansible connectivity
- Validation tooling

---

# Routing Architecture

## OSPF

Single-area design:

```text
Area 0
```

Primary links:

```text
CAT8K-1 <-> CAT9K
172.16.0.0/30

CAT8K-2 <-> CAT9K
172.16.0.4/30
```

Objectives:

- Route validation
- Automation exercises
- OSPF deployment testing
- Compliance verification

---

# Automation Host

The automation host is the operational center of the platform.

## Responsibilities

- Source control
- Python execution
- Ansible execution
- Docker runtime
- pyATS execution
- Artifact storage

Repository location:

```text
/opt/labrepo
```

---

# Python Environment

A dedicated Python virtual environment is created during bootstrap.

Purpose:

- Dependency isolation
- Reproducibility
- Safe package management

Activation:

```bash
enter-lab
```

---

# Ansible Architecture

Ansible provides configuration management and infrastructure automation.

## Components

```text
ansible/
├── inventory/
├── playbooks/
├── group_vars/
├── host_vars/
└── ansible.cfg
```

## Responsibilities

- Device configuration
- OSPF deployment
- ACL deployment
- State collection
- Compliance validation

---

# pyATS Architecture

pyATS executes inside Docker rather than on the host.

Container:

```text
ciscotestautomation/pyats:latest
```

Benefits:

- Dependency isolation
- Easy upgrades
- Consistent execution
- Host cleanliness

---

## Persistent Mounts

```text
Host                             Container

/opt/labrepo/pyats       -->     /pyats

/opt/labrepo             -->     /workspace

/opt/labrepo/artifacts/
pyats-runs               -->     /artifacts
```

---

# Artifact Strategy

PROJECT-AUTOCOR intentionally stores artifacts for every significant operation.

Purpose:

- Troubleshooting
- Historical review
- Auditability
- Repeatability

---

## Ansible Artifacts

```text
artifacts/ansible-runs/
```

Example:

```text
artifacts/ansible-runs/
└── 20260510-153001/
    ├── console.log
    └── run_meta.txt
```

---

## pyATS Artifacts

```text
artifacts/pyats-runs/
```

Example:

```text
artifacts/pyats-runs/
└── 20260510-161522/
```

---

# Bootstrap Architecture

Bootstrap is responsible for creating a fully operational automation host.

Location:

```text
bootstrap/automation-host/bootstrap.sh
```

---

## Major Bootstrap Stages

### System Preparation

Installs:

- Git
- Python
- Pip
- Virtual environment tooling
- Network utilities

---

### Docker Installation

Installs:

- Docker Engine
- Docker CLI
- Docker Compose support

---

### Python Environment

Creates:

```text
/opt/labrepo/.venv
```

---

### Ansible Installation

Installs required automation tooling.

---

### pyATS Runtime

Pulls:

```text
ciscotestautomation/pyats:latest
```

Creates:

```text
/opt/labrepo/pyats
/opt/labrepo/artifacts/pyats-runs
```

Validates ownership and permissions.

---

# Secrets Management

Secrets are intentionally excluded from source control.

Files:

```text
~/.ansible/.vault_env
~/.ansible/get_vault_pass.sh
```

This approach allows:

- Local secret storage
- Vault integration
- Git safety

---

# Future Architecture Direction

Planned capabilities include:

## Terraform

Infrastructure provisioning and lifecycle management.

---

## GitLab CI/CD

Pipeline-based validation and testing.

---

## RESTCONF

Infrastructure state management through API-driven workflows.

---

## FastMCP

AI-assisted infrastructure operations.

---

## Compliance Frameworks

Validation of:

- Interface state
- Routing state
- Configuration drift
- Operational readiness

---

# Architectural Philosophy

Treat the lab itself as infrastructure.

Automation code, validation logic, and operational tooling should remain modular, portable, and reproducible.

The objective is not merely to automate devices, but to build an automation platform capable of supporting future operational and engineering workflows.
