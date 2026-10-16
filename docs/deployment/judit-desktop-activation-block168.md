# RagV local desktop/Judit activation — Block 168

This is an **operator preparation record**, not an approval to deploy or submit a provider request. No production migration, container replacement, backup, provider request, or secret change was performed for this block.

## Observed installation and scope

Observation date: 2026-10-16. The habitual shortcut is `RagV Desktop.lnk` → `scripts/start-ragv-hidden.vbs` → `scripts/start-ragv-desktop.ps1`. It uses the developer stack in `compose.yaml`, project `ragv`, and persistent PostgreSQL volume `ragv_rpy_pgdata`. This is not the immutable-image production Compose deployment.

Read-only checks found:

- PostgreSQL migration ledger: `033_claim_semantic_verification.sql`; migration 034 has only been exercised in disposable PostgreSQL.
- The database has zero tenant rows, processes, tenant-process links, Judit requests, queue jobs, attachments, and tracking rows. No authorized reference process is present.
- The workspace `.env` declares `JUDIT_API_KEY` but its value is empty. The running API and both workers have no nonempty Judit key. The API has one Bearer-token mapping, but its tenant row is absent.
- `JUDIT_CALLBACK_URL` is empty and the current developer `compose.yaml` does not pass it to workers. Production Compose does pass this value to workers and requires it.
- Judit attachment acquisition and DataJud are disabled. DataJud has no automatic fallback from Judit.
- The active API serves old frontend assets. The Block 167 frontend/desktop changes are local and have not been installed.

Repeat these checks immediately before any later activation; counts and secret configuration can change. Never print token values, provider keys, callback URLs, or raw process data into an operational transcript.

## Credential and request boundaries

- `JUDIT_API_KEY` is an opaque provider secret, sent by a worker as Judit's `api-key` HTTP header. `_api_key()` trims whitespace; no `Bearer ` prefix is used. It belongs in the existing secret source, not in frontend configuration.
- In this developer installation, Compose interpolates the root `D:\projetos\ragv\.env`; the key is injected into `worker-1` and `worker-2`, not the API. Keep `.env` uncommitted and ACL-restricted. For production, set it in the secret-managed env file passed to `scripts/deploy_production.py --env-file ...`; production Compose injects it into workers only. Do not put it in chat, source code, the API environment, or the desktop executable.
- The browser's `Authorization: Bearer ...` is a separate Rpy tenant credential configured by `RPY_BEARER_TOKENS`. It authenticates the user to the Rpy API; it is not a Judit credential. The API key is never sent to the browser.
- For callback-driven completion, `JUDIT_CALLBACK_URL` must be a stable public HTTPS endpoint whose path matches `/webhooks/judit/<JUDIT_WEBHOOK_TOKEN>`. It is sensitive because it contains the webhook token. The current local Compose file does not wire this setting, and the habitual installation has no public callback configured. A key alone therefore does not establish end-to-end acquisition/finalization readiness.
- `JUDIT_ATTACHMENTS_ENABLED=false` is the safe default. Enabling it is a separate decision: the request asks Judit for attachments, workers download from the lawsuits host, and the production egress allowlist must include that exact host. The parser extracts text locally; the database stores attachment metadata, hashes and derived chunks, not the downloaded raw bytes.

## Request lifecycle, billing and duplicate protection

1. `GET /processes/{cnj}/status` / `precheck` classifies Rpy's tenant-scoped database state. It does not call Judit. `/ready` only reports API/database readiness and is not a Judit connectivity test.
2. The UI requires an explicit action. `POST /processes/{cnj}/authorizations` issues a single-use, 15-minute token bound to tenant, CNJ, source `judit`, and operation `acquisition` or `refresh`.
3. `POST /processes/{cnj}/request` consumes that authorization and durably records/enqueues work. The worker sends `POST https://requests.prod.judit.io/requests/` with `search.search_type=lawsuit_cnj`, `search.search_key=<CNJ>` and `with_attachments=false` under the current default. The optional callback URL is added only when configured.
4. Judit returns a request ID. A configured webhook stages responses; `request_completed` queues finalization. Finalized process versions, movements, summary and access records are stored in PostgreSQL. With attachment acquisition enabled, extracted text chunks are stored separately for retrieval.
5. Rpy serializes a tenant/CNJ request row and deduplicates queue work with a database idempotency key. Acquisition jobs have one worker attempt. Rpy does **not** send a provider-side idempotency key with the POST, so end-to-end exactly-once billing is not guaranteed. An ambiguous timeout/5xx/transport result becomes `failed_ambiguous` and automatic retry is blocked; an operator must first resolve whether Judit accepted the request. Explicitly retryable provider rejections require a later user action. Do not bypass this guard or clear the state to “try again.”
6. A process already in tenant history is a `refresh` and requires a fresh explicit confirmation. A repeated request may be billed even if Judit serves cached data, according to the repository's provider-acceptance contract.

The documented non-creating diagnostic is `python scripts/provider_live_smoke.py --diagnose-judit` (GET `/requests?page=1&page_size=1`). It is not a documented authentication-validation endpoint, does not prove that a paid POST is permitted by the account plan, and was **not run** here. Any provider call still requires the operator to review the current contract and authorize the exact probe/request.

The repository contains no monetary tariff. The estimated Judit charge is therefore **unknown**; obtain the current account-specific price/plan before authorization. A successful acquisition may also trigger a separately billable model summary if the generation provider is configured. Attachment download is separately disabled by default. Do not infer total cost from a synthetic test or from a successful HTTP response.

## Provider-free test evidence

The following tests use synthetic fixtures and patched provider functions; they demonstrate Rpy orchestration and database contracts, not Judit connectivity, contract pricing, real process quality, or production behavior:

- `staging_evidence_block168/postgres-smoke.json` and `.log`: 35 PostgreSQL 16 integration tests passed against disposable PostgreSQL, including migration repeatability, precheck, explicit authorization, queue/worker execution, duplicate protection, callback persistence/finalization, tenant history, attachment chunk persistence, and ambiguous/retryable recovery. Provider credentials were blank and no provider network calls were made.
- `staging_evidence_block167/validation.json` and screenshots: real isolated PyWebView UI check, synthetic history, tenant isolation, migration 033→034, and a cancelled refresh-confirmation dialog. It contained no documents/chunks/embeddings, so it did not exercise real retrieval or a real RAG answer.
- Targeted frontend/desktop tests and browser smoke passed. A broader Windows unit run had 1,118 passed, 1 skipped, and 12 platform-specific failures: Unix-domain asyncio APIs and `/bin/sh` are unavailable in this host environment.

## Controlled local installation update (not executed)

Do not use the habitual shortcut as the migration procedure. Its PowerShell script rebuilds only `api` and then runs `docker compose up --no-build`; it does not rebuild the `migrate` or worker images from the current checkout. With schema 033, this can leave the updated API paired with old migration/worker images. The following sequence is for a separately scheduled, approved local maintenance window only.

1. Confirm the target is explicitly `-p ragv -f compose.yaml`; inspect services, volume, migration ledger, pending jobs, tracking rows and all old container image IDs/tags. Do not use `down -v`, volume pruning, production Compose, or the production deploy runner. If queued work or trackings exist, resolve them before giving workers a provider key.
2. Close the desktop window. Build all application services from the reviewed local commit while the old containers remain running: `docker compose -p ragv -f compose.yaml build migrate api worker-1 worker-2 scheduler`. Preserve the prior image IDs/tags for rollback; do not prune images.
3. Stop writers but leave PostgreSQL and its volume running: `docker compose -p ragv -f compose.yaml stop api worker-1 worker-2 scheduler`.
4. Create a custom-format `pg_dump` to a new ACL-restricted directory outside the repository and outside the database volume. For this developer stack, one Windows-safe path is to run `pg_dump -U rpy -d rpy --format=custom --no-owner --no-acl --file=/tmp/rpy-pre-034.dump` inside `ragv-postgres-1`, then `docker cp` that file to the restricted host directory. Verify `pg_restore --list`, compute/record SHA-256 for the host copy, copy the dump and checksum to encrypted off-host storage, and verify the retrieved copy. Restore it into a **separate disposable PostgreSQL/pgvector database** and check the migration ledger, vector extension, and representative counts before considering it a recovery point. Never restore over the live volume as a test.
5. With the original PostgreSQL service healthy and app writers stopped, run the named one-shot migration service using the new image: `docker compose -p ragv -f compose.yaml up --no-deps migrate`. Require exit code 0. Verify `schema_migrations` ends at `034_acquisition_authorizations.sql` and the 034 authorization/history relations exist. Migration 034 is additive and transactionally recorded; do not drop it during rollback.
6. Start the new API/workers/scheduler without rebuilding: `docker compose -p ragv -f compose.yaml up -d --no-build api worker-1 worker-2 scheduler`. Verify container health, `/ready`, migration ledger, `/` title/brand, `/favicon.svg`, and served JS/CSS. `/ready` proves only API/database reachability.
7. Build the desktop executable to a temporary output directory with the local `.venv-desktop` PyInstaller environment and `RagVDesktop.spec`; verify the embedded icon before replacing the old executable. Keep a separate copy of the old executable. Open the actual PyWebView window and inspect its title, branding, access panel, provider selection, history and confirmation flow. Do not confirm a paid action. The live database currently has no tenant/process rows, so this verifies the UI shell only; use an authorized tenant/data set for any history/RAG validation.
8. Only after deployment is separately approved, provision Judit credentials in the secret source and recreate workers deliberately. Re-check queue/tracking state immediately beforehand. Do not combine credential activation with this schema/frontend update.

### Recovery

- If build or backup verification fails, leave old running containers unchanged (or restart the stopped old containers); do not migrate.
- If migration fails, do not start the new API/workers. The per-migration transaction and checksum ledger should leave migration 034 unapplied. Restore old image tags and start the old services.
- If migration 034 succeeds but the new application fails, restore the saved old application image tags and restart the old services. Keep schema 034 in place: it is additive and the 033 application does not depend on it. Do not roll back by dropping tables or restoring the backup over live data.
- A database restore is disaster recovery, not routine code rollback. Preserve the failed database separately and require explicit data-loss approval before any restore to the live target. Never remove `ragv_rpy_pgdata`.

## Real-request gate

| Item | Current state |
|---|---|
| Judit credential | **Absent** from `.env` and active workers; configure via the existing secret source, not chat |
| End-to-end callback | **Absent** locally; `JUDIT_CALLBACK_URL` is not passed by current developer Compose |
| Operation | **Pending**: first `acquisition` or confirmed `refresh` must be named |
| Authorized CNJ | **Pending**; none supplied |
| Tenant authorization | **Blocked**: one configured Bearer mapping has no matching tenant row; no processes/data |
| Estimated Judit price | **Unknown**; request is contract-billed even when cached; obtain current account-specific pricing |
| Duplicate safeguards | Local row/queue/auth guards pass synthetic PostgreSQL tests; no provider idempotency key; ambiguous outcomes require manual resolution |
| Installation | Stale API/frontend; schema 033; persistent volume retained; no changes made |
| Attachments / RAG | Attachments disabled; no chunks/embeddings; real document retrieval not tested |

Until credential, callback, tenant/data, operation, CNJ, price and explicit approval are resolved, **do not submit a Judit POST**.
