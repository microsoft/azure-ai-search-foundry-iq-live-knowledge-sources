# External Tenant Login

Use this when you need to test Fabric Ontology Knowledge Source with a tenant that is different from your normal Microsoft/internal Azure CLI profile.

The helper script isolates Azure CLI cache with `AZURE_CONFIG_DIR`, so your internal tenant session remains separate.

## 1. Create A Local Env File

Create `.env.external.local` at the repo root:

```bash
EXTERNAL_TENANT_ID=<external-tenant-guid>
EXTERNAL_AZURE_CONFIG_DIR=~/.azure-foundry-iq-ext
```

`.env.external.local` is ignored by git.

## 2. Login

```bash
scripts/external-tenant-login.sh --env-file .env.external.local
```

If browser login is awkward, use device code:

```bash
scripts/external-tenant-login.sh --env-file .env.external.local --device-code
```

## 3. Check Existing Session

```bash
scripts/external-tenant-login.sh --env-file .env.external.local --check-only
```

## 4. Get A Raw Search Token

For local Fabric KS retrieve testing:

```bash
scripts/external-tenant-login.sh --env-file .env.external.local --print-token
```

Pass the printed token as the raw value of:

```http
x-ms-query-source-authorization: <raw-token>
```

Do not prefix it with `Bearer`.

## Notes

- The script cannot bypass MFA or Conditional Access.
- If Chrome shows an account picker and the external admin account is already signed in, selecting that account can complete the login.
- If extra verification is required, the user must complete it.
- Do not commit tenant IDs, tokens, or generated local env files.
