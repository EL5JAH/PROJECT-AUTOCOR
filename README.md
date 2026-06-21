# PROJECT-AUTOCOR

**Portable Cisco Automation Lab Platform**

PROJECT-AUTOCOR is a reproducible automation environment designed for Cisco automation, infrastructure engineering, and network operations workflows.

Originally created as a Cisco AUTOCOR study platform, the project has evolved into a reusable automation engineering lab focused on:

- Python automation
- Ansible
- Cisco IOS-XE automation
- pyATS testing
- Docker-based tooling
- Git workflows
- Infrastructure validation
- Network automation experimentation

The platform is intended to provide a repeatable environment for developing, testing, validating, and documenting automation solutions.

---

# Objectives

PROJECT-AUTOCOR is designed to:

- Provide a repeatable automation lab environment
- Standardize tooling across deployments
- Keep host systems reproducible
- Support infrastructure validation
- Enable portable development workflows
- Serve as a foundation for future automation projects

---

# Current Capabilities

## Platform Services

- Automated Ubuntu bootstrap
- Python virtual environment provisioning
- Docker Engine installation
- pyATS Docker runtime
- Ansible automation framework
- Git integration
- Optional local GitLab CE deployment

## Validation

- Baseline infrastructure validation
- Environment health checks
- Execution logging
- Artifact collection

## Developer Experience

- Guided MOTD
- Environment helper commands
- Automated dependency installation
- Reproducible lab builds

---

# Architecture Overview

```text
                     GitHub / GitLab
                             |
                             |
                             v

+--------------------------------------------------+
|               Automation Host                    |
|--------------------------------------------------|
| Ubuntu Server                                    |
| Python Virtual Environment                       |
| Ansible                                          |
| Docker                                           |
| pyATS Runtime                                    |
| Git Tooling                                      |
+--------------------------------------------------+
                 |                    |
                 |                    |
                 v                    v

       +----------------+    +----------------+
       | Cisco Devices  |    | pyATS Docker   |
       | CML Topology   |    | Runtime        |
       +----------------+    +----------------+
```

The automation host serves as the operational center of the platform while pyATS executes inside Docker for dependency isolation and reproducibility.

---

# Repository Layout

```text
PROJECT-AUTOCOR/
│
├── ansible/
│
├── bootstrap/
│   └── automation-host/
│
├── cml/
│
├── gitlab/
│
├── lab-validator/
│
├── pyats/
│
├── scripts/
│
├── tests/
│
├── utils/
│
├── artifacts/
│
├── docs/
│   ├── QUICKSTART.md
│   └── ARCHITECTURE.md
│
├── CHANGELOG.md
├── VERSION.txt
└── requirements.txt
```

Refer to Architecture.md for detailed topology and component documentation.

---

# Core Components

## Bootstrap

Location:

```text
bootstrap/automation-host/
```

Responsibilities:

- System preparation
- Python environment creation
- Docker installation
- pyATS runtime deployment
- Ansible configuration
- Helper command installation
- Optional GitLab deployment

---

## Ansible

Location:

```text
ansible/
```

Responsibilities:

- Device configuration
- Infrastructure automation
- Inventory management
- State collection
- Validation workflows

Execution artifacts are stored under:

```text
artifacts/ansible-runs/
```

---

## pyATS

Location:

```text
pyats/
```

pyATS runs inside Docker to isolate dependencies from the host operating system.

Benefits:

- Consistent execution
- Reproducible testing
- Persistent artifacts
- Simplified upgrades

Execution artifacts are stored under:

```text
artifacts/pyats-runs/
```

---

## Lab Validator

Location:

```text
lab-validator/
```

Purpose:

- Baseline validation
- Infrastructure verification
- Connectivity testing
- Compliance checking

---

## GitLab

Location:

```text
gitlab/
```

Local GitLab CE support is optional and disabled by default to reduce bootstrap time and resource consumption.

---

# Artifact Collection

PROJECT-AUTOCOR stores execution artifacts to support troubleshooting, auditing, and historical review.

## Ansible Artifacts

```text
artifacts/ansible-runs/
```

## pyATS Artifacts

```text
artifacts/pyats-runs/
```

Each execution generates a timestamped run directory containing logs and metadata.

---

# Documentation

| Document        | Purpose                               |
| --------------- | ------------------------------------- |
| QUICKSTART.md   | Initial setup and daily usage         |
| ARCHITECTURE.md | Detailed platform and topology design |
| CHANGELOG.md    | Version history and project evolution |

---

# Current Version

```text
v0.8.2
```

Refer to CHANGELOG.md for release history and platform evolution.

---

# Future Direction

Planned areas of expansion include:

- Terraform workflows
- RESTCONF automation
- Expanded pyATS test coverage
- CI/CD integration
- Compliance validation frameworks
- AI-assisted operational tooling

PROJECT-AUTOCOR is intended to be treated as automation infrastructure rather than a collection of isolated scripts. New functionality should be modular, reproducible, and portable.
