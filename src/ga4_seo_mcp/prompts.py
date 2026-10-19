"""MCP prompts: guided GA4, SEO and site-launch workflows."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def audit_ga4_setup(property_id: str) -> str:
    """Audit the measurement setup of a GA4 property: streams, key events, dimensions, Ads links."""
    return f"""Audit the measurement setup of GA4 property '{property_id}':

1. **Property and data streams**
   - Call `get_property` for the property settings (time zone, currency).
   - Call `list_data_streams` to check the configured web and app streams.

2. **Key events**
   - Call `list_key_events` for the declared key events.
   - Call `events_summary` (last 7 days) and compare: key events that never fire, and frequent
     events that are not key events but probably should be.

3. **Custom dimensions**
   - Call `list_custom_dimensions` and check which event and user parameters are registered.

4. **Google Ads**
   - Call `list_google_ads_links` to see whether the property is linked to Google Ads.

5. **Deliverable**
   - A Markdown report with a 1-10 health score and concrete fixes for every gap.
"""


def seo_360_audit(site_url: str, property_id: str) -> str:
    """360° audit of organic search and web performance (Search Console + GA4 + PageSpeed)."""
    return f"""Run a 360° SEO and performance audit of '{site_url}' (GA4 property '{property_id}'):

1. **Organic search (Search Console)**
   - Find the matching site with `sc_list_sites`.
   - `sc_top_queries` for the last 28 days: clicks, impressions, CTR and position.
   - `sc_page_performance` for the main landing pages.

2. **On-site behavior (GA4)**
   - `top_pages` and `traffic_sources` for active users, session duration and bounce rate.

3. **Speed and user experience (PageSpeed Insights)**
   - `psi_audit` on the home page for mobile and desktop.
   - `psi_field_data_only` for real-user Core Web Vitals when CrUX has data.

4. **Synthesis**
   - A table of SEO opportunities: pages with many impressions but low CTR, or high bounce rate.
   - The 3 most urgent actions.
"""


def portfolio_performance_digest(property_ids: str) -> str:
    """Consolidated performance digest for several GA4 properties.

    Args:
        property_ids: comma-separated GA4 property IDs, e.g. '123456789,987654321'.
    """
    pids = [p.strip() for p in property_ids.split(",") if p.strip()]
    pids_repr = ", ".join(f"'{p}'" for p in pids)
    return f"""Build a consolidated digest for GA4 properties [{pids_repr}]:

1. Call `audit_portfolio` with that list for the last 7 days.
2. Show a comparison table: sessions, active users, conversions and bounce rate per property.
3. Highlight the best performer and the property that dropped the most or needs attention.
"""


def launch_site_measurement(site_url: str) -> str:
    """Guided end-to-end measurement setup for a site: plan, confirm, apply, verify, baseline."""
    return f"""Set up the measurement of '{site_url}' end to end. Never change anything without the
user's explicit confirmation.

1. **Find the account**: call `list_account_summaries` and ask the user which GA4 account should
   own the site, plus the time zone and currency for a new property.
2. **Plan**: call `bootstrap_site_measurement` with apply=False. Ask the user which key events
   (e.g. generate_lead) and custom dimensions they want, and include them.
3. **Confirm**: show the plan as a table (what exists, what will be created) and wait for an
   explicit "yes". If the response says writes are disabled, tell the user to restart the server
   with --enable-writes and stop here.
4. **Apply**: call `bootstrap_site_measurement` again with the same arguments and apply=True.
   Report every step and give the user the measurement ID (G-...) to install.
5. **Verify the domain in Search Console**: give the user the DNS TXT record from the report.
   When they confirm it is published, call `sc_verify_site_dns`. If it fails, wait a minute and
   retry; DNS propagation can take a while.
6. **Sitemap**: once verified, call `sc_submit_sitemap` with the site's sitemap URL
   (usually /sitemap.xml) and confirm with `sc_list_sitemaps`.
7. **Baseline**: call `psi_audit` for mobile and desktop and save the scores and Core Web Vitals
   as the launch baseline.
8. **Summary**: a checklist of what was created, what is pending for the user (install the tag,
   publish the TXT record) and the PageSpeed baseline.
"""


PROMPTS = (audit_ga4_setup, seo_360_audit, portfolio_performance_digest, launch_site_measurement)


def register(mcp: FastMCP) -> None:
    for fn in PROMPTS:
        mcp.prompt()(fn)
