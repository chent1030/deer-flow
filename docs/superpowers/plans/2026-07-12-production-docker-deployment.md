# Production Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single-host Docker production configuration for `https://ai.ruisiyi.com.cn` with internal PostgreSQL, automatic Let's Encrypt TLS, and AIO Docker sandboxes.

**Architecture:** Extend the existing production Compose stack instead of replacing its Gateway/Nginx routing. PostgreSQL and Certbot become internal stack services; `scripts/deploy.sh` bootstraps the first certificate before starting TLS Nginx, while the existing AIO mode detector loads the Docker-socket overlay. Runtime secrets stay in ignored `.env`, and `config.yaml` references environment variables only.

**Tech Stack:** Docker Compose, Nginx, Certbot, PostgreSQL 17 Alpine, Bash, YAML, pytest.

---

## File Map

- `backend/tests/test_production_compose.py`: parse the production Compose and Nginx files and enforce database, TLS, port, health, and persistence invariants.
- `backend/tests/test_deploy_tls.py`: execute `scripts/deploy.sh` against a fake Docker binary and enforce certificate bootstrap and service selection.
- `docker/docker-compose.yaml`: define PostgreSQL, Certbot renewal/bootstrap, shared certificate volumes, health dependencies, and public ports.
- `docker/nginx/nginx.conf`: serve ACME challenges, redirect HTTP, terminate TLS, and retain the current API/SSE proxy routes.
- `scripts/deploy.sh`: validate production TLS inputs, bootstrap the first certificate, start PostgreSQL/Certbot, and report the HTTPS URL.
- `.env`: ignored production secrets and public-origin settings.
- `config.yaml`: active model, PostgreSQL, run-event, and AIO sandbox configuration.
- `.env.example`, `README.md`, `AGENTS.md`: document the production variables and deployment lifecycle without real credentials.

### Task 1: Lock The Production Compose Contract

**Files:**
- Create: `backend/tests/test_production_compose.py`
- Modify: `docker/docker-compose.yaml`

- [ ] **Step 1: Write failing topology tests**

Create tests that load `docker/docker-compose.yaml` with `yaml.safe_load` and assert the exact production invariants:

```python
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose.yaml"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_production_postgres_is_private_persistent_and_healthy():
    compose = _compose()
    postgres = compose["services"]["postgres"]
    assert postgres["image"] == "postgres:17-alpine"
    assert "ports" not in postgres
    assert "postgres-data:/var/lib/postgresql/data" in postgres["volumes"]
    assert postgres["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
    assert "postgres-data" in compose["volumes"]


def test_gateway_waits_for_postgres_health():
    depends_on = _compose()["services"]["gateway"]["depends_on"]
    assert depends_on["postgres"]["condition"] == "service_healthy"
    assert depends_on["redis"]["condition"] == "service_healthy"


def test_tls_services_share_certificate_and_challenge_volumes():
    compose = _compose()
    nginx = compose["services"]["nginx"]
    certbot = compose["services"]["certbot"]
    assert nginx["ports"] == ["${HTTP_PORT:-80}:80", "${HTTPS_PORT:-443}:443"]
    assert "certbot-certs:/etc/letsencrypt:ro" in nginx["volumes"]
    assert "certbot-webroot:/var/www/certbot:ro" in nginx["volumes"]
    assert "certbot-certs:/etc/letsencrypt" in certbot["volumes"]
    assert "certbot-webroot:/var/www/certbot" in certbot["volumes"]
```

- [ ] **Step 2: Run the tests and confirm the expected failure**

Run: `cd backend && uv run pytest tests/test_production_compose.py -q`

Expected: failures for missing `postgres` and `certbot` services and the old `2026` Nginx port.

- [ ] **Step 3: Add PostgreSQL and certificate services**

Modify `docker/docker-compose.yaml` to add:

```yaml
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-deerflow}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
      POSTGRES_DB: ${POSTGRES_DB:-deerflow}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 20
    networks: [deer-flow]
    restart: unless-stopped

  certbot:
    image: certbot/certbot:v4.0.0
    entrypoint: /bin/sh
    command: -c 'trap exit TERM; while :; do certbot renew --webroot -w /var/www/certbot --quiet; sleep 12h & wait $${!}; done'
    volumes:
      - certbot-certs:/etc/letsencrypt
      - certbot-webroot:/var/www/certbot
    networks: [deer-flow]
    restart: unless-stopped
```

Change Nginx host ports to 80/443, mount both shared volumes read-only, add the periodic `nginx -s reload`, and make Gateway depend on healthy PostgreSQL. Add `postgres-data`, `certbot-certs`, and `certbot-webroot` under top-level `volumes`.

- [ ] **Step 4: Run the topology tests**

Run: `cd backend && uv run pytest tests/test_production_compose.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the topology change**

```bash
git add backend/tests/test_production_compose.py docker/docker-compose.yaml
git commit -m "feat(docker): add production postgres and certificate services"
```

### Task 2: Add Nginx TLS Termination Without Breaking Streaming

**Files:**
- Modify: `backend/tests/test_production_compose.py`
- Modify: `docker/nginx/nginx.conf`

- [ ] **Step 1: Add failing Nginx assertions**

Append tests for the exact TLS and routing contract:

```python
NGINX_PATH = REPO_ROOT / "docker" / "nginx" / "nginx.conf"


def test_nginx_terminates_tls_and_redirects_plain_http():
    nginx = NGINX_PATH.read_text(encoding="utf-8")
    assert "listen 80;" in nginx
    assert "location ^~ /.well-known/acme-challenge/" in nginx
    assert "return 301 https://$host$request_uri;" in nginx
    assert "listen 443 ssl;" in nginx
    assert "/etc/letsencrypt/live/${DEER_FLOW_DOMAIN}/fullchain.pem" in nginx
    assert "/etc/letsencrypt/live/${DEER_FLOW_DOMAIN}/privkey.pem" in nginx


def test_tls_nginx_keeps_sse_and_gateway_forwarding():
    nginx = NGINX_PATH.read_text(encoding="utf-8")
    assert "rewrite ^/api/langgraph/(.*) /api/$1 break;" in nginx
    assert "proxy_buffering off;" in nginx
    assert "proxy_set_header X-Accel-Buffering no;" in nginx
    assert "proxy_read_timeout 600s;" in nginx
    assert "proxy_set_header X-Forwarded-Proto https;" in nginx
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `cd backend && uv run pytest tests/test_production_compose.py -q`

Expected: the new TLS assertions fail against the current port-2026 server.

- [ ] **Step 3: Split HTTP redirect and HTTPS proxy servers**

Update `docker/nginx/nginx.conf` so the HTTP server only serves the webroot and redirects:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name ${DEER_FLOW_DOMAIN};

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
```

Move all existing proxy locations into a `listen 443 ssl` server, use the live certificate paths for `${DEER_FLOW_DOMAIN}`, set modern TLS protocols, and force `X-Forwarded-Proto https`. Preserve the existing upload limits, streaming settings, runtime DNS resolution, and API rewrites verbatim.

- [ ] **Step 4: Run Nginx and Gateway routing tests**

Run: `cd backend && uv run pytest tests/test_production_compose.py tests/test_gateway_runtime_cleanup.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit TLS routing**

```bash
git add backend/tests/test_production_compose.py docker/nginx/nginx.conf
git commit -m "feat(nginx): terminate production TLS"
```

### Task 3: Bootstrap And Renew Certificates Through The Deploy Script

**Files:**
- Create: `backend/tests/test_deploy_tls.py`
- Modify: `scripts/deploy.sh`
- Modify: `docker/docker-compose.yaml`

- [ ] **Step 1: Write failing deploy-script tests**

Use a temporary worktree and fake `docker` executable, following `test_deploy_uv_extras.py`. Capture Docker arguments and assert:

```python
def test_deploy_requires_tls_identity(tmp_path):
    result = _run_deploy(tmp_path, env_updates={"DEER_FLOW_DOMAIN": "", "CERTBOT_EMAIL": ""})
    assert result.returncode != 0
    assert "DEER_FLOW_DOMAIN" in result.stderr


def test_deploy_bootstraps_missing_certificate_before_up(tmp_path):
    result, calls = _run_deploy(
        tmp_path,
        env_updates={
            "DEER_FLOW_DOMAIN": "ai.ruisiyi.com.cn",
            "CERTBOT_EMAIL": "chent1030@hotmail.com",
        },
        certificate_exists=False,
    )
    assert result.returncode == 0
    assert any("certonly --standalone" in call for call in calls)
    bootstrap_index = next(i for i, call in enumerate(calls) if "certonly --standalone" in call)
    up_index = next(i for i, call in enumerate(calls) if " up " in f" {call} ")
    assert bootstrap_index < up_index
```

The helper must fake the certificate probe separately from bootstrap and must never store or print `.env` values.

- [ ] **Step 2: Run the deploy tests and confirm failure**

Run: `cd backend && uv run pytest tests/test_deploy_tls.py -q`

Expected: failures because the deploy script does not validate TLS variables or run Certbot.

- [ ] **Step 3: Add a profile-scoped bootstrap service**

Add this service to `docker/docker-compose.yaml` so normal renewal never competes for port 80:

```yaml
  certbot-bootstrap:
    image: certbot/certbot:v4.0.0
    profiles: [certbot-bootstrap]
    ports:
      - "${HTTP_PORT:-80}:80"
    volumes:
      - certbot-certs:/etc/letsencrypt
    networks: [deer-flow]
```

- [ ] **Step 4: Implement deploy preflight and bootstrap**

In `scripts/deploy.sh`, after sandbox mode detection and before `up`:

```bash
require_env() {
    local name="$1"
    local value="${!name:-}"
    if [ -z "$value" ]; then
        echo -e "${RED}✗ $name is required for production HTTPS.${NC}" >&2
        exit 1
    fi
}

require_env DEER_FLOW_DOMAIN
require_env CERTBOT_EMAIL

if ! "${COMPOSE_CMD[@]}" run --rm --no-deps --entrypoint sh certbot \
    -c "test -f /etc/letsencrypt/live/$DEER_FLOW_DOMAIN/fullchain.pem" >/dev/null 2>&1; then
    "${COMPOSE_CMD[@]}" --profile certbot-bootstrap run --rm --service-ports certbot-bootstrap \
        certonly --standalone --non-interactive --agree-tos \
        --email "$CERTBOT_EMAIL" -d "$DEER_FLOW_DOMAIN"
fi
```

Include `postgres` and `certbot` in the normal production service list, keep `certbot-bootstrap` profile-only, and change the success banner to `https://${DEER_FLOW_DOMAIN}`.

- [ ] **Step 5: Run deploy and sandbox-mode tests**

Run: `cd backend && uv run pytest tests/test_deploy_tls.py tests/test_deploy_uv_extras.py tests/test_docker_sandbox_mode_detection.py -q`

Expected: all tests pass, including AIO overlay detection.

- [ ] **Step 6: Commit certificate bootstrap**

```bash
git add backend/tests/test_deploy_tls.py scripts/deploy.sh docker/docker-compose.yaml
git commit -m "feat(deploy): bootstrap and renew letsencrypt certificates"
```

### Task 4: Write The Ignored Production Environment And Runtime Config

**Files:**
- Modify, do not commit: `.env`
- Modify, do not commit: `config.yaml`

- [ ] **Step 1: Read and classify provider secrets without displaying values**

Read `/Users/chentao/Documents/Obsidian Vault/Daily/数字资产.md`, associate the value following each DeepSeek, Kimi, and MiniMax label, and validate only that every value is non-empty. Do not print the values or pass them on a command line.

- [ ] **Step 2: Generate independent production secrets**

Generate at least 32 random bytes for `POSTGRES_PASSWORD`, `BETTER_AUTH_SECRET`, and `DEER_FLOW_INTERNAL_AUTH_TOKEN`. Percent-encode the PostgreSQL password when constructing `DATABASE_URL` so URL-reserved bytes cannot corrupt parsing.

- [ ] **Step 3: Update `.env`**

Preserve existing search credentials. Write `DEEPSEEK_API_KEY`,
`MOONSHOT_API_KEY`, and `MINIMAX_API_KEY` from their classified source entries.
Write `POSTGRES_PASSWORD`, `BETTER_AUTH_SECRET`, and
`DEER_FLOW_INTERNAL_AUTH_TOKEN` from the three independently generated random
values. Construct `DATABASE_URL` from the literal user/database/host values
below and the percent-encoded PostgreSQL password. Then write the public values:

```dotenv
POSTGRES_USER=deerflow
POSTGRES_DB=deerflow
UV_EXTRAS=postgres
DEER_FLOW_DOMAIN=ai.ruisiyi.com.cn
CERTBOT_EMAIL=chent1030@hotmail.com
DEER_FLOW_TRUSTED_ORIGINS=https://ai.ruisiyi.com.cn
GATEWAY_CORS_ORIGINS=https://ai.ruisiyi.com.cn
GATEWAY_ENABLE_DOCS=false
```

The implemented `.env` must contain the actual secret values and the complete
`postgresql://deerflow:...@postgres:5432/deerflow` URL. It must not contain
descriptive stand-ins.

- [ ] **Step 4: Activate the three models in `config.yaml`**

Use the repository's documented adapters and current China-region endpoints:

```yaml
models:
  - name: deepseek-chat
    display_name: DeepSeek Chat
    use: deerflow.models.patched_deepseek:PatchedChatDeepSeek
    model: deepseek-chat
    api_key: $DEEPSEEK_API_KEY
    timeout: 600.0
    max_retries: 2
    max_tokens: 8192
    supports_thinking: false
    supports_vision: false

  - name: kimi-k2.5
    display_name: Kimi K2.5
    use: deerflow.models.patched_deepseek:PatchedChatDeepSeek
    model: kimi-k2.5
    api_base: https://api.moonshot.cn/v1
    api_key: $MOONSHOT_API_KEY
    timeout: 600.0
    max_retries: 2
    max_tokens: 32768
    supports_thinking: true
    supports_vision: true

  - name: minimax-m3
    display_name: MiniMax M3
    use: deerflow.models.patched_minimax:PatchedChatMiniMax
    model: MiniMax-M3
    api_key: $MINIMAX_API_KEY
    base_url: https://api.minimaxi.com/v1
    request_timeout: 600.0
    max_retries: 2
    max_tokens: 4096
    temperature: 1.0
    supports_vision: true
    supports_thinking: true
```

Retain the documented Kimi and MiniMax thinking toggles from `config.example.yaml`. Change persistence and sandbox sections to:

```yaml
database:
  backend: postgres
  postgres_url: $DATABASE_URL

run_events:
  backend: db
  max_trace_content: 10240
  track_token_usage: true

sandbox:
  use: deerflow.community.aio_sandbox:AioSandboxProvider
  image: enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.11.0
  replicas: 3
  bash_output_max_chars: 20000
  read_file_output_max_chars: 50000
  ls_output_max_chars: 20000
  bash_command_timeout: 600
```

- [ ] **Step 5: Validate without leaking secrets**

Run a YAML parser for `config.yaml`, `scripts/detect_uv_extras.py`, and a key-name-only `.env` audit. Expected results: YAML parses; detected extras include `postgres`; sandbox mode is `aio`; every required environment key reports `configured` without its value.

### Task 5: Document And Verify The Production Release

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Document non-secret production variables**

Add `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `DEER_FLOW_DOMAIN`, `CERTBOT_EMAIL`, `HTTP_PORT`, and `HTTPS_PORT` to `.env.example` with safe example values. Explain that `make up` performs first certificate issuance and that DNS plus inbound 80/443 are prerequisites.

- [ ] **Step 2: Update operator and architecture docs**

Update `README.md` with the exact production sequence:

```bash
cp .env.example .env
cp config.example.yaml config.yaml
# Set production values, then:
make up
docker compose --env-file .env -p deer-flow -f docker/docker-compose.yaml ps
```

Update `AGENTS.md` service topology and production notes to include internal PostgreSQL, Certbot, ports 80/443, AIO DooD auto-detection, and the Docker-socket security boundary.

- [ ] **Step 3: Run focused tests**

Run:

```bash
cd backend && uv run pytest \
  tests/test_production_compose.py \
  tests/test_deploy_tls.py \
  tests/test_deploy_uv_extras.py \
  tests/test_docker_sandbox_mode_detection.py \
  tests/test_gateway_runtime_cleanup.py \
  tests/test_compose_default_workers.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run formatting and static validation**

Run:

```bash
cd backend && uv run ruff check tests/test_production_compose.py tests/test_deploy_tls.py
cd backend && uv run ruff format --check tests/test_production_compose.py tests/test_deploy_tls.py
docker compose --env-file .env -p deer-flow -f docker/docker-compose.yaml -f docker/docker-compose.dood.yaml config --quiet
git diff --check
```

Expected: every command exits zero. Do not run `docker compose config` without `--quiet`, because its rendered output contains secrets.

- [ ] **Step 5: Commit documentation and retain local secrets**

```bash
git add .env.example README.md AGENTS.md
git commit -m "docs: add secure production docker deployment"
git status --short
```

Expected: committed source and documentation are clean; ignored `.env` and `config.yaml` remain available locally and are not staged.

- [ ] **Step 6: Report production-host checks**

The handoff must state that real certificate issuance and end-to-end service health remain production-host checks. On the server, verify DNS resolution, inbound 80/443, `docker compose ps`, `curl -I http://ai.ruisiyi.com.cn`, `curl -I https://ai.ruisiyi.com.cn/health`, login, one call per model, restart persistence, and creation/removal of an AIO sandbox container.
