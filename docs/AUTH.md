# Authentication

`ga4-seo-mcp` uses [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) (ADC) through `google.auth.default()`. That gives you two routes; pick one.

| | Your own OAuth client (user login) | Service account |
|---|---|---|
| Acts as | You | A robot identity you grant access to |
| Setup | One-time: consent screen + Desktop OAuth client | One-time: create the account + a JSON key, add its email to each property/site |
| Best for | Your own sites, quick start, writes on everything you manage | Read-only access to a few properties, CI, servers, Docker |
| Search Console domain verification | ✅ | ✅ (the service account becomes the owner) |

PageSpeed Insights needs no Google login at all; DataForSEO uses its own credentials.

---

## Scopes per toolset

The server never asks for more than the toolsets you enable. Each Google client requests only the scope of the call it makes (reads use the read-only scope even when writes are on).

| Toolset | Read-only | Added by `--enable-writes` |
|---|---|---|
| `admin` | `analytics.readonly` | `analytics.edit` |
| `data` | `analytics.readonly` | — |
| `gsc` | `webmasters.readonly` | `webmasters`, `siteverification` |
| `psi` | — | — |
| `dataforseo` | — | — |
| `ads` | `adwords` | — |

`ga4-seo-mcp auth-command [--toolsets …] [--enable-writes] [--client-id-file …]` prints the `gcloud` login for exactly that set. It also adds `cloud-platform`, **only to the login command**: `gcloud auth application-default login --scopes=…` refuses to run without it (`cloud-platform scope is required but not requested`). The server's API clients never request `cloud-platform`.

Service accounts get exactly the scopes requested at runtime. User credentials keep whatever was consented at login, so re-run `auth-command` after enabling a new toolset or writes. `ga4-seo-mcp doctor` tells you when the token is missing a scope.

---

## Route A — your own OAuth client

Google blocks sensitive scopes such as Analytics and Search Console on gcloud's built-in OAuth client ("This app is blocked"). The fix is a Desktop OAuth client in a Google Cloud project you own.

1. Pick or create a project (e.g. `my-gcp-project`) in the [Google Cloud console](https://console.cloud.google.com/).
2. **Enable the APIs** you will use: Google Analytics Admin API, Google Analytics Data API, Google Search Console API, and (for writes on GSC) Site Verification API. For the `ads` toolset, also Google Ads API.
3. **OAuth consent screen** (Google Auth Platform → Branding / Audience): user type *External*, publishing status *Testing*. Under **Test users**, add the Google account that owns your GA4 properties. While the app is in *Testing* and unverified, only listed test users can sign in, and Google shows an "unverified app" warning you can accept for your own account.
4. **Create an OAuth client ID** of type **Desktop app** and download the JSON (e.g. `oauth-client.json`). Keep it out of any repository; the project's `.gitignore` already ignores `oauth-client*.json`.
5. Log in:

   ```bash
   ga4-seo-mcp auth-command --client-id-file=oauth-client.json            # read-only
   ga4-seo-mcp auth-command --client-id-file=oauth-client.json --enable-writes
   # run the printed gcloud command, then:
   gcloud auth application-default set-quota-project my-gcp-project
   ga4-seo-mcp doctor
   ```

Why your own client and not a shared one: these scopes are *sensitive*, and a published app that requests them needs Google's verification. A personal client in *Testing* mode skips that for the test users you list. That is also why this project does not ship a client ID.

## Route B — service account

1. In your project, create a service account and a JSON key (IAM & Admin → Service accounts → Keys). Store it with `chmod 600`, outside any repository.
2. Grant it access where it must act:
   - **GA4**: Admin → Property access management → add the service account email with **Viewer** (read-only) or **Editor** (to use writes).
   - **Search Console**: Settings → Users and permissions → add the email as **Full** (read) or **Owner** (sitemaps, verification).
3. Point ADC at the key:

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   ga4-seo-mcp doctor
   ```

   In Docker: `-v /path/to/service-account.json:/creds/sa.json:ro -e GOOGLE_APPLICATION_CREDENTIALS=/creds/sa.json`.

A service account cannot create a GA4 *account*, and it only sees the properties you add it to — which is exactly what you want for least privilege.

---

## Non-Google credentials

| Toolset | Variables | Notes |
|---|---|---|
| `psi` | `PAGESPEED_API_KEY` (optional) | Without a key you share Google's anonymous quota, which is often exhausted (HTTP 429). Restrict the key to the PageSpeed Insights API. |
| `dataforseo` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | Paid API; every call spends credit. |
| `ads` | `GOOGLE_ADS_DEVELOPER_TOKEN` or `~/.config/ga4-seo-mcp/dev-token` (`chmod 600`, otherwise refused) | Optional `GOOGLE_ADS_LOGIN_CUSTOMER_ID` for manager (MCC) accounts. Without active spend, volumes are bucketed. |

These values are read from the environment (or that one file) only, never logged and never included in error messages.
