# Production Docker Deployment Design

## Goal

Prepare DeerFlow for a single-host production deployment at
`https://ai.ruisiyi.com.cn` using Docker Compose. The deployment must include
an internal PostgreSQL database, automatic Let's Encrypt certificates, and
container-isolated AIO sandboxes without Kubernetes.

## Scope

The change updates the local production configuration and the repository's
Docker production stack. It covers:

- production environment variables and model credentials;
- DeepSeek, Kimi, and MiniMax model configuration;
- PostgreSQL persistence inside Docker Compose;
- AIO sandbox execution through Docker-out-of-Docker (DooD);
- HTTPS termination in DeerFlow's Nginx service;
- automatic certificate issuance and renewal with Certbot; and
- configuration and Compose validation.

The deployment itself is not executed from this workstation. Certificate
issuance requires the domain to resolve to the production host and inbound TCP
ports 80 and 443 to reach that host.

## Environment And Secrets

The project-root `.env` remains the single environment source consumed by the
Gateway and Docker Compose. AI provider credentials are read from the user's
`Documents/Obsidian Vault/Daily/数字资产.md` file and written only to `.env`.
The values must never be copied into committed YAML, documentation, command
output, or completion messages.

The deployment uses credentials for DeepSeek, Kimi, and MiniMax. PostgreSQL
does not reuse the database details from the source document because the user
selected an internal PostgreSQL container. A new high-entropy PostgreSQL
password is generated locally. Authentication and internal Gateway tokens are
also generated independently.

Production environment settings include:

- public origin `https://ai.ruisiyi.com.cn`;
- Let's Encrypt contact `chent1030@hotmail.com`;
- PostgreSQL connection through the Compose service name `postgres`;
- the `postgres` backend extra for the Gateway image;
- exact trusted-origin and CORS values for the public origin; and
- disabled public API documentation.

## Application Configuration

`config.yaml` exposes one supported model entry for each available credential:
DeepSeek, Kimi K2.5, and MiniMax. Each entry references an environment variable
instead of embedding a secret. Provider URLs and model identifiers follow the
existing examples in `config.example.yaml` and the current provider adapters.

The database backend changes from SQLite to PostgreSQL through
`$DATABASE_URL`. Run events use the database backend so production traces
survive restarts. The background scheduler remains disabled unless it is
already intentionally enabled by the user.

The sandbox provider changes from `LocalSandboxProvider` to
`AioSandboxProvider`, pins the documented `1.11.0` multi-architecture sandbox
image, and limits active sandboxes to three. No `provisioner_url` is configured,
so the existing deploy script detects pure-Docker AIO mode and automatically
loads `docker-compose.dood.yaml`.

## Docker Topology

The production Compose stack contains Nginx, Frontend, Gateway, Redis,
PostgreSQL, and Certbot. PostgreSQL is available only on the internal Compose
network, has a health check, and persists data in a named volume. Gateway waits
for PostgreSQL and Redis health before starting.

Nginx exposes host ports 80 and 443. Port 80 serves the ACME challenge and
redirects other traffic to HTTPS. Port 443 terminates TLS and preserves the
existing same-origin routing, streaming, upload limits, and forwarded headers.
PostgreSQL, Redis, Gateway, and Frontend do not publish host ports.

Certificate files and ACME challenge files use named volumes shared by Nginx
and Certbot. Initial certificate bootstrap occurs before the TLS Nginx
configuration starts, preventing startup failure caused by missing certificate
files. The Certbot service periodically runs renewal, and Nginx reloads the
renewed certificate without dropping the application stack.

## Sandbox Security Boundary

Pure-Docker AIO mode mounts the host Docker socket into Gateway. This grants
the Gateway container root-equivalent control over the Docker host. The
existing opt-in overlay and mode detection are retained so the socket is
mounted only when AIO mode is selected. The sandbox image is version-pinned,
sandbox concurrency is bounded, and sandbox containers are not directly
published through Nginx.

This is the supported approach for an isolated sandbox on a Docker-only host,
but host compromise remains possible if the Gateway itself is compromised.
Kubernetes provisioner mode is explicitly out of scope.

## Failure Handling

- Deployment stops before startup when required domain, email, database, or
  provider variables are missing.
- PostgreSQL health failure prevents Gateway startup rather than silently
  falling back to SQLite.
- Certificate bootstrap failure leaves HTTPS disabled and reports the Certbot
  error; it does not start Nginx with an invalid TLS configuration.
- Renewal failure retains the last valid certificate and is visible in Certbot
  logs.
- A missing or inaccessible Docker socket fails the existing AIO preflight.

## Verification

Verification must not print environment values. It includes:

1. YAML parsing for `config.yaml` and all modified Compose files.
2. `docker compose config` with secrets redacted from any reported output.
3. Project configuration preflight and sandbox mode detection.
4. Focused Docker sandbox mode tests and any deployment-script tests affected
   by the implementation.
5. Static checks that PostgreSQL has persistence and health gating, internal
   services do not publish ports, Nginx routes preserve SSE behavior, and the
   public trusted origin is exact.
6. On the production host, DNS, ports 80/443, certificate issuance, container
   health, HTTPS redirect, login, model invocation, persistence across restart,
   and creation of an AIO sandbox container.

## Deployment Outcome

Running the documented production bootstrap on a prepared Linux Docker host
starts the complete stack. Users reach DeerFlow only through
`https://ai.ruisiyi.com.cn`; application state persists in PostgreSQL and named
volumes; agent shell and file work executes in per-thread AIO sandbox
containers; and certificates renew automatically.
