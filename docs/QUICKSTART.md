# PROJECT-AUTOCOR Quick Start

This guide provides the fastest path from a fresh automation host to a working PROJECT-AUTOCOR environment.

---

# Prerequisites

Recommended environment:

- Ubuntu Server 24.04 LTS
- Cisco Modeling Labs (CML)
- Internet connectivity
- GitHub access
- 4 vCPU minimum
- 8 GB RAM minimum

Recommended:

- 8 vCPU
- 16 GB RAM

---

# Clone Repository

```bash
git clone <repo-url>
cd PROJECT-AUTOCOR
```

---

# Bootstrap Environment

Run bootstrap as root:

```bash
sudo ./bootstrap/automation-host/bootstrap.sh
```

Bootstrap performs:

- System updates
- Package installation
- Python setup
- Docker installation
- Ansible installation
- pyATS runtime setup
- Helper command installation

---

# Verify Bootstrap

Check bootstrap status:

```bash
bootstrap-status
```

Expected output:

```text
Bootstrap Status: SUCCESS
```

---

# Enter Lab Environment

Activate the project environment:

```bash
enter-lab
```

This will:

- Change to the repository root
- Activate Python virtual environment
- Display current Git branch
- Verify Docker access

---

# Verify Environment Health

Run:

```bash
lab check
```

Verify:

- Python environment
- Docker access
- Repository integrity
- Tool availability

---

# Configure Secrets

Run:

```bash
setup_local_secrets.sh
```

This configures:

```text
~/.ansible/.vault_env
~/.ansible/get_vault_pass.sh
```

Never commit secrets to Git.

---

# Update Repository

Before beginning work:

```bash
git pull
```

---

# Run Ansible

Example:

```bash
run_ansible.sh playbooks/configure-ospf.yml
```

Artifacts are stored in:

```text
artifacts/ansible-runs/
```

---

# Run pyATS

Verify pyATS:

```bash
run-pyats pyats version check
```

Launch interactive shell:

```bash
pyats-shell
```

Open a Bash session inside the container:

```bash
run-pyats bash
```

Artifacts are stored in:

```text
artifacts/pyats-runs/
```

---

# Common Commands

## Enter Environment

```bash
enter-lab
```

## Leave Environment

```bash
exit-lab
```

## Environment Health

```bash
lab check
```

## Bootstrap Status

```bash
bootstrap-status
```

## pyATS Shell

```bash
pyats-shell
```

---

# Typical Workflow

Start work:

```bash
enter-lab
git pull
lab check
```

Run automation:

```bash
run_ansible.sh <playbook>
```

Run testing:

```bash
run-pyats <command>
```

Review artifacts:

```bash
ls artifacts/
```

Commit changes:

```bash
git add .
git commit -m "description"
git push
```

---

# Troubleshooting

## Docker Permission Issues

Verify current user belongs to docker group:

```bash
groups
```

Expected:

```text
docker
```

If missing:

```bash
sudo usermod -aG docker $USER
logout
```

Log back in and retry.

---

## pyATS Permission Errors

Verify directories exist:

```bash
ls -ld /opt/labrepo/pyats
ls -ld /opt/labrepo/artifacts/pyats-runs
```

Expected owner:

```text
cisco:cisco
```

Repair permissions:

```bash
sudo chown -R cisco:cisco \
    /opt/labrepo/pyats \
    /opt/labrepo/artifacts/pyats-runs
```

---

## Bootstrap Failed

Review logs:

```bash
less /var/log/automation-bootstrap.log
```

Check status:

```bash
cat /var/log/automation-bootstrap.status
```

---

# Next Steps

Recommended progression:

1. Validate lab connectivity
2. Run baseline validation
3. Execute Ansible playbooks
4. Create pyATS tests
5. Integrate Git workflows
6. Expand automation use cases

PROJECT-AUTOCOR is intended to be a reusable automation platform. Treat the lab as infrastructure and keep automation code, validation logic, and operational tooling modular and portable.
