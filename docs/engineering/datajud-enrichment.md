# DataJud enrichment contract

Rpy treats DataJud as an optional official metadata enrichment source. Judit remains
the source for parties and movement text. DataJud may contribute class/TPU code,
subjects, adjudicating body and county when those values are present in the public
response.

## Activation boundary

The adapter is disabled by default.

Production activation requires all of the following:

- `DATAJUD_ENABLED=true`;
- `DATAJUD_AUTHORIZED_USE=true`, set only after deployment/product/legal review;
- `DATAJUD_API_KEY` containing the current public CNJ key;
- public, non-secret process data only.

The key is intentionally not stored in source code or fixtures. A `401` or `403`
is returned to the pipeline as `auth_error` because the CNJ public key may rotate.
Transport failures, throttling and server failures are `unavailable`; they must
not invalidate the Judit version.

## Authenticated UI lookup path

The frontend submits `POST /processes/datajud/jobs` with `{"code": "<cnj>"}` and
a client-generated `Idempotency-Key`. The API authenticates the bearer/API key,
applies its CNJ scope, and persists a `lookup_datajud_metadata` job in the
PostgreSQL queue. The UI polls `POST /processes/datajud/jobs/status` with the CNJ
and job ID; the job payload and result are only readable by the tenant that
submitted that CNJ. Replays return the same job, while reusing a key for a
different CNJ is rejected. Job results follow the configured job-retention policy.
The `/processos` API aliases use the same contract.

Only workers receive `DATAJUD_API_KEY` and perform provider requests. The API
receives only the non-secret enablement/authorization flags and does not call the
DataJud adapter directly. Do not add API credentials or provider egress to the API
service to work around worker configuration; the provider-enabled worker network
boundary remains authoritative. If worker configuration is missing, the job fails
closed and the API returns a generic unavailable response.

## Current public API contract

Reviewed on 2026-09-17.

The CNJ public API uses tribunal-specific Elasticsearch-compatible endpoints:

```
POST https://api-publica.datajud.cnj.jus.br/api_publica_<alias>/_search
Authorization: APIKey <current public key>
Content-Type: application/json
```

Rpy queries the canonical 20-digit process number and requests at most one hit.
The tribunal alias is derived from the CNJ `J.TR` fields for supported segments.
Unsupported segment/TR combinations fail closed and do not fan out across aliases.

Relevant official/current references:

- https://www.cnj.jus.br/sistemas/datajud/api-publica/
- https://atos.cnj.jus.br/atos/detalhar/6972
- https://www.cnj.jus.br/programas-e-acoes/numeracao-unica/perguntas-frequentes/
- https://atos.cnj.jus.br/atos/detalhar/119

## Use restrictions

Portaria CNJ n. 374/2026 amended the public DataJud rules. The reviewed text states
that public API/open-data consumption is subject to legal, non-commercial and
authorized use, prohibits modification/distribution/sale or commercial exploitation
of the supplied data, and requires attribution to CNJ/DataJud in publications,
applications and studies.

For that reason, presence of the adapter in Rpy is **not** authorization to enable
it in every deployment. The explicit `DATAJUD_AUTHORIZED_USE` gate exists so
commercial or otherwise incompatible environments cannot enable DataJud merely by
setting a technical API key.

## Data minimization and secrecy

- `secrecy_level > 0` returns `skipped_secrecy` before any transport call.
- Raw DataJud HTTP payloads are not persisted by this adapter.
- The normalized merge contract stores only modeled metadata/provenance.
- Parties and movement text are never sourced from DataJud by this enrichment path.
- Provider credentials must never be logged or added to audit metadata.

## Best-effort behavior

DataJud enrichment is supplementary. `disabled`, `not_found`, `auth_error` and
`unavailable` do not erase, duplicate or invalidate a valid Judit process version.
Conflict handling remains deterministic: when official metadata is available,
DataJud wins only for the modeled metadata fields and the Judit/DataJud disagreement
is persisted and surfaced in `Pontos de atenção`.
