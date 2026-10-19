# Tools

Generated from the live registry by `scripts/gen_tools_doc.py`; do not edit by hand.

Write tools only exist when the server starts with `--enable-writes`.
`bootstrap_site_measurement` is always registered with the `admin` toolset; its
`apply=True` mode needs `--enable-writes`.

## `admin` (9 read, 10 write)

Scopes: `analytics.readonly` · with writes: `analytics.edit`

| Tool | Kind | Description |
|---|---|---|
| `list_account_summaries` | read | List every GA4 account you can access, with a summary of its properties. |
| `list_properties` | read | List the GA4 properties under an account. |
| `get_property` | read | Get the full settings of a GA4 property (time zone, currency, industry, type). |
| `list_data_streams` | read | List the data streams (web, iOS, Android) of a GA4 property. |
| `get_data_stream` | read | Get one data stream, including the measurement ID of a web stream. |
| `list_key_events` | read | List the key events (formerly conversions) declared on a GA4 property. |
| `list_custom_dimensions` | read | List the custom dimensions declared on a GA4 property, with their scope. |
| `list_google_ads_links` | read | List the links between a GA4 property and Google Ads accounts. |
| `create_property` | write | Create a GA4 property under an account. |
| `update_property` | write, destructive | Change the display name, time zone or currency of a GA4 property. |
| `delete_property` | write, destructive | Move a GA4 property to the trash. |
| `create_web_data_stream` | write | Create a web data stream for a site and return its measurement ID (G-XXXXXXX). |
| `update_web_data_stream` | write, destructive | Change the display name or default URI of a web data stream. Pass at least one. |
| `delete_data_stream` | write, destructive | Permanently delete a data stream. The site stops sending data to this property. |
| `create_key_event` | write | Mark an event name as a key event (formerly called a conversion). |
| `create_custom_dimension` | write | Register an event or user parameter as a custom dimension. |
| `create_google_ads_link` | write | Link a GA4 property to a Google Ads account. |
| `delete_google_ads_link` | write, destructive | Remove a link between a GA4 property and a Google Ads account. |
| `bootstrap_site_measurement` | read (plan); write with `apply=True` | Plan, and optionally apply, the full measurement setup of a website. |

## `data` (8 read, 0 write)

Scopes: `analytics.readonly`

| Tool | Kind | Description |
|---|---|---|
| `run_report` | read | Run a flexible GA4 report. |
| `run_realtime_report` | read | Realtime report for the last 30 minutes. |
| `top_pages` | read | Top pages by sessions, with active users, bounce rate and average session duration. |
| `events_summary` | read | Count of every event that fired, to audit what is actually being measured. |
| `traffic_sources` | read | Top traffic sources (source / medium) with sessions, active users and conversions. |
| `conversions_summary` | read | Conversions and total users per event name: a summary of the active key events. |
| `web_vitals_summary` | read | Core Web Vitals reported by your own site as GA4 events. |
| `audit_portfolio` | read | Summary metrics for several GA4 properties in one call. |

## `gsc` (5 read, 3 write)

Scopes: `webmasters.readonly` · with writes: `webmasters`, `siteverification`

| Tool | Kind | Description |
|---|---|---|
| `sc_list_sites` | read | List the Search Console sites you can access. |
| `sc_top_queries` | read | Top search queries with clicks, impressions, CTR (%) and average position. |
| `sc_page_performance` | read | Top pages in Google Search by clicks, with impressions, CTR (%) and average position. |
| `sc_query_breakdown_by_page` | read | Which search queries bring traffic to one specific page. |
| `sc_list_sitemaps` | read | List the sitemaps submitted for a Search Console site, with errors and warnings. |
| `sc_submit_sitemap` | write | Submit (or resubmit) a sitemap to Search Console. |
| `sc_add_site_and_get_verify_token` | write | Add a domain property to Search Console and return the DNS TXT record that verifies it. |
| `sc_verify_site_dns` | write | Verify ownership of a domain property whose DNS TXT record is already published. |

## `psi` (2 read, 0 write)

Scopes: none

| Tool | Kind | Description |
|---|---|---|
| `psi_audit` | read | Run a PageSpeed Insights audit (Lighthouse lab test + CrUX field data) on a public URL. |
| `psi_field_data_only` | read | Only the CrUX field data (real Chrome users, p75 over 28 days) for a URL and its origin. |

## `dataforseo` (2 read, 0 write)

Scopes: none

| Tool | Kind | Description |
|---|---|---|
| `kw_ideas` | read | Discover long-tail keyword ideas related to one or more seed keywords (DataForSEO Labs). |
| `kw_volume` | read | Exact monthly search volume and CPC for queries you already know (DataForSEO). |

## `ads` (2 read, 0 write)

Scopes: `adwords`

| Tool | Kind | Description |
|---|---|---|
| `kw_ideas_gads` | read | Discover keyword ideas from seed keywords with Google Ads Keyword Planner. |
| `kw_volume_gads` | read | Historical metrics from Google Ads Keyword Planner for queries you already know. |

## Prompts

| Prompt | Arguments | Description |
|---|---|---|
| `audit_ga4_setup` | `property_id` | Audit the measurement setup of a GA4 property: streams, key events, dimensions, Ads links. |
| `seo_360_audit` | `site_url`, `property_id` | 360° audit of organic search and web performance (Search Console + GA4 + PageSpeed). |
| `portfolio_performance_digest` | `property_ids` | Consolidated performance digest for several GA4 properties. |
| `launch_site_measurement` | `site_url` | Guided end-to-end measurement setup for a site: plan, confirm, apply, verify, baseline. |
