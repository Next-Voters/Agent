# Email Lambda: SES → Mailgun + SSM Migration (Handoff Prompt)

The Terraform infrastructure (`infrastructure/`) was migrated off Amazon SES to
**Mailgun**, and all secrets now live in **SSM Parameter Store** instead of being
passed as plaintext. The Email Lambda's **application code lives in a separate
repo/image** and still calls SES — it must be patched to match the new contract.

> **How to use this doc:** open a Claude Code session (or hand a ticket) in the
> **email Lambda repo** and paste the **Prompt** section below. The
> **Reference implementation** and **Verification** sections give it everything
> needed to finish without guessing.

---

## Prompt

> Patch this Lambda to send report emails via **Mailgun** instead of Amazon SES,
> and to read all secrets from **AWS SSM Parameter Store** at runtime. The
> infrastructure (IAM, env vars, SSM parameters) is already provisioned by
> Terraform in the platform repo — do **not** add IAM or change how the function
> is deployed. Implement only the application code.
>
> **Runtime environment variables the function now receives** (set by Terraform
> `infrastructure/lambda.tf` — treat these names as a fixed contract):
>
> | Env var | Meaning | Kind |
> |---|---|---|
> | `SHARE_BASE_URL` | Public base URL for report links, no trailing slash | plain value |
> | `MAILGUN_DOMAIN` | Mailgun sending domain (e.g. `mg.example.org`) | plain value |
> | `MAILGUN_SENDER` | `From` header (e.g. `Next Voters <noreply@mg.example.org>`) | plain value |
> | `MAILGUN_BASE_URL` | Mailgun API base (`https://api.mailgun.net`, or `…eu…` for EU) | plain value |
> | `MAILGUN_API_KEY_PARAM` | **Name** of the SSM SecureString holding the Mailgun API key | SSM param name |
> | `SUPABASE_URL_PARAM` | **Name** of the SSM param holding the Supabase URL | SSM param name |
> | `SUPABASE_KEY_PARAM` | **Name** of the SSM param holding the Supabase key | SSM param name |
>
> The `*_PARAM` variables hold SSM parameter **names** (e.g.
> `/next-voters/staging/MAILGUN_API_KEY`), not the secret values. Fetch the value
> with `ssm:GetParameter`/`GetParameters` using `WithDecryption=True`.
>
> **IAM already granted to the function's role** (assume it; don't re-create it):
> `ssm:GetParameter`/`ssm:GetParameters` on exactly those three parameters,
> `kms:Decrypt` gated to SSM, `sqs:ReceiveMessage`/`DeleteMessage`/
> `GetQueueAttributes` on the report-ready queue, and CloudWatch Logs. **There is
> no longer any `ses:*` permission.**
>
> **Requirements:**
> 1. On cold start, fetch the Mailgun API key and the Supabase URL/key from SSM
>    using the `*_PARAM` env vars. Cache the decrypted values at module scope so
>    warm invocations don't re-call SSM. Never log secret values.
> 2. Keep the existing Supabase read (the SQS body is `{"region", "report_id"}`;
>    load the report + headers by `report_id`) — only swap the credential source
>    to SSM.
> 3. Build all report links from `SHARE_BASE_URL` (e.g.
>    `f"{SHARE_BASE_URL}/reports/{report_id}"`).
> 4. Send via the Mailgun messages API:
>    `POST {MAILGUN_BASE_URL}/v3/{MAILGUN_DOMAIN}/messages`, HTTP basic auth
>    `("api", <mailgun_api_key>)`, `from = MAILGUN_SENDER`. Call
>    `raise_for_status()` so non-2xx fails the invocation.
> 5. **Let exceptions propagate.** The SQS event source mapping is `batch_size=1`
>    with `maxReceiveCount=3` → failures redrive to the email DLQ. Do not
>    swallow errors or return success on failure.
> 6. Remove the boto3 SES client and all `send_email`/`send_raw_email` calls.
> 7. Add `requests` to the image's dependencies if not already present (or use
>    `urllib` to avoid the dependency — see the reference note).
>
> Use the reference implementation below as the SSM + Mailgun layer; keep your
> existing report-fetch, recipient-resolution, and template-rendering logic.

---

## Reference implementation (Python)

### `ssm.py` — cached secret fetch (the SSM fetch)

```python
"""Runtime SSM Parameter Store reads with warm-invocation caching.

The Lambda runtime sets AWS_REGION, so boto3 picks the right region/endpoint.
The function is not in a VPC, so it reaches SSM over the public endpoint.
"""

import boto3

_ssm = boto3.client("ssm")
_cache: dict[str, str] = {}


def get_secret(param_name: str) -> str:
    """Fetch + decrypt one SSM SecureString, caching across warm invocations."""
    if param_name not in _cache:
        resp = _ssm.get_parameter(Name=param_name, WithDecryption=True)
        _cache[param_name] = resp["Parameter"]["Value"]
    return _cache[param_name]


def get_secrets(param_names: list[str]) -> dict[str, str]:
    """Batch-fetch multiple SSM SecureStrings in one call; results keyed by name."""
    missing = [n for n in param_names if n not in _cache]
    if missing:
        resp = _ssm.get_parameters(Names=missing, WithDecryption=True)
        for p in resp["Parameters"]:
            _cache[p["Name"]] = p["Value"]
        invalid = resp.get("InvalidParameters", [])
        if invalid:
            raise RuntimeError(f"SSM parameters missing/denied: {invalid}")
    return {n: _cache[n] for n in param_names}
```

> **Cache + rotation note:** `_cache` lives for the warm container's lifetime, so after a secret is rotated in SSM, warm instances keep serving the old value until they recycle (cold start). Accepted cold-start/cost trade-off; if you need immediate rotation, add a short TTL or clear the cache per invocation.

### `mailgun.py` — send via Mailgun

```python
"""Mailgun send. Replaces the previous SES client.

Uses `requests` for brevity. To avoid the dependency, the same call can be made
with urllib.request + base64 basic-auth + urlencoded form body.
"""

import os

import requests

from ssm import get_secret


def send_email(*, to: list[str], subject: str, html: str, text: str | None = None) -> None:
    base = os.environ["MAILGUN_BASE_URL"]
    domain = os.environ["MAILGUN_DOMAIN"]
    api_key = get_secret(os.environ["MAILGUN_API_KEY_PARAM"])

    data = {"from": os.environ["MAILGUN_SENDER"], "to": to, "subject": subject, "html": html}
    if text:
        data["text"] = text

    resp = requests.post(
        f"{base}/v3/{domain}/messages",
        auth=("api", api_key),
        data=data,
        timeout=30,
    )
    resp.raise_for_status()  # non-2xx -> raises -> SQS redrive -> email DLQ
```

### `handler.py` — wiring (keep your existing report/render logic)

```python
import json
import os

from ssm import get_secrets
from mailgun import send_email


def _supabase():
    names = [os.environ["SUPABASE_URL_PARAM"], os.environ["SUPABASE_KEY_PARAM"]]
    creds = get_secrets(names)
    from supabase import create_client
    return create_client(creds[names[0]], creds[names[1]])


def handler(event, context):
    client = _supabase()
    for record in event["Records"]:
        msg = json.loads(record["body"])              # {"region", "report_id"}

        report = fetch_report(client, msg["report_id"])          # <-- existing logic
        html, text = render_email(                               # <-- existing logic
            report, share_base_url=os.environ["SHARE_BASE_URL"]
        )
        send_email(
            to=recipients_for(report),                          # <-- existing logic
            subject=subject_for(report),                        # <-- existing logic
            html=html,
            text=text,
        )
    # No try/except around the loop: a failure must surface so SQS can redrive.
```

`fetch_report`, `render_email`, `recipients_for`, `subject_for` are placeholders
for the function's existing logic — port them from the SES version unchanged
except for sourcing credentials from SSM and rendering links from
`SHARE_BASE_URL`.

---

## Verification

**Local (against staging):** export the seven env vars (point `*_PARAM` at the
real `/next-voters/staging/...` names), use AWS creds that can read those params,
and invoke the handler with a sample event
`{"Records":[{"body":"{\"region\":\"toronto\",\"report_id\":1}"}]}`. Confirm a
Mailgun `200` and a delivered message.

**Deployed:** send a test message to the `report-ready` SQS queue and check
CloudWatch for: SSM fetch succeeded, Mailgun returned 2xx, no SES API calls, and
links contain `SHARE_BASE_URL`. A bad Mailgun key should land the message in the
email DLQ after 3 attempts (proves error propagation works).

---

## Provisioning the SSM secret values (one-time, per environment)

Terraform creates the parameters as placeholders; set the real values
out-of-band (they never enter this repo or `*.tfvars`). Note that a later
`terraform refresh`/`apply` **will** read the decrypted values into Terraform
state, so keep state in the encrypted remote backend stubbed in
`infrastructure/main.tf`:

```bash
for kv in \
  "MAILGUN_API_KEY=key-..." \
  "SUPABASE_URL=https://xxxx.supabase.co" \
  "SUPABASE_KEY=ey..."; do
  name="${kv%%=*}"; val="${kv#*=}"
  aws ssm put-parameter --overwrite --type SecureString \
    --name "/next-voters/staging/${name}" --value "${val}"
done
```

(The pipeline ECS task additionally uses `OPENAI_API_KEY`, `TAVILY_API_KEY`,
`TOGETHER_API_KEY` under the same prefix — see `infrastructure/ssm.tf`.)
