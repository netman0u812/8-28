---
name: cisco-sna-architecture
description: Use for Cisco Secure Network Analytics (CSNA/SNA) deployment architecture at CVS Health — the corrected 8-site independent environment model (Shea, RI1-2100 Corporate, RI1-2100 Retail, EQ-VA, EQ-DAL, Windsor, Middletown, Vegas), each a full Collector + Flow Broker + Storage stack, plus the Phase 2 outlier-site backlog (Santa Clara, Atlanta QTS, Honolulu, Pittsburgh, San Antonio, CME-HUB, CMC-HUB). Also covers Flow Collector/Broker placement, telemetry sourcing (NetFlow, FTD, PAN-OS IPFIX/App-ID, ISE pxGrid, 128T SD-WAN, Cisco Telemetry Broker), detection coverage scoring, XDR/Splunk/ISE integration, and CCD Platform-derived host group governance. Trigger on "SNA," "CSNA," "Secure Network Analytics," "Flow Collector," "Flow Broker," "SNA-MGR," "ODID," "pxGrid," "EQ-VA," "EQ-DAL," or "ETA," even if "SNA" isn't spelled out. Do not confuse with "Secure Network Access" (NAC) — see nac-ztna-fpms/forescout-hw-refresh instead. Also consult cvs-netsec-context for org facts and ccd-platform-data-model for the underlying IPAM/LM datasets.
---

# Cisco Secure Network Analytics (CSNA) — 8-Site Independent Environment Architecture

Source: "Cisco Secure Network Analytics — Enterprise Deployment Vision & Strategy," CVS Health InfoSec / CCD Platform, v1.0, 2026-05-19, DRAFT (original five-stack domain framing — see "Superseded framing" below), corrected and reconciled by Michael J. Martin against `netflow_fw_collector_mapping.xlsx` (197-firewall FW-to-Collector dataset, 2026). Data basis: IPAM v3.78, location_master v5.9g, retail_networks v2.8 (326,809 records total), netflow_fw_collector_mapping.xlsx.

## Core thesis

CVS Health's network — 15+ years of acquisitions culminating in the 2018 Aetna merger, four overlapping RFC1918 spaces, six routing domains, 11,000 retail locations, SNAT-masked SD-WAN — cannot run a single SNA Manager. **45 confirmed IP collisions** between CVS and Aetna routing domains (public space, RFC1918, GCP BU allocations, even 203.0.113.0 documentation space) mean a shared Manager would build composite behavioral baselines for fictional entities, producing unreliable alerts in both directions. **Independent Manager + Collector + Flow Broker + Data Store environments per physical site eliminate this by construction.** Zero physical traffic taps required anywhere in the design.

Cross-domain correlation happens *above* SNA, in Cisco XDR (entity-based: user identity, hostname, cert fingerprint — not IP), and in Splunk (domain-tagged event retention/hunting).

## As-built architecture: 8 independent CSNA environments (Phase 1)

Each of the 8 sites below runs its **own full independent CSNA environment** — Collector, Flow (Telemetry) Broker, and Storage, not a shared Manager spanning sites. This is the corrected, as-deployed model; it replaces the "five domain-based stacks" framing the original 2026-05-19 vision doc used (see "Superseded framing" below for how the two map to each other).

| # | Site | Site code(s) | Role |
|---|---|---|---|
| 1 | Shea (Scottsdale, AZ) | SCT | CVS enterprise DC |
| 2 | RI1-2100 Corporate (Cumberland + Woonsocket, RI) | CLD / WON | CVS enterprise DC — corporate/enterprise traffic |
| 3 | RI1-2100 Retail | CLD / WON (same physical site, separate environment) | Retail — 128T SD-WAN hub telemetry, logically independent from RI1-2100 Corporate despite sharing a location |
| 4 | EQ-VA — Equinix Ashburn, VA | EXV | Colo — B2B/partner connectivity |
| 5 | EQ-DAL — Equinix Dallas, TX | EXT | Colo — B2B/partner connectivity |
| 6 | Windsor, CT | WDC-Windsor | Aetna enterprise |
| 7 | Middletown, CT | MID / MDC-Middletown | Aetna enterprise |
| 8 | Vegas | LAS-VEGAS-COLO | COLO |

Cross-referenced against `netflow_fw_collector_mapping.xlsx` (197 firewalls: 171 Cisco, 4 Palo Alto; sourced B2B/PCI/VPN/EGRESS): 179 of 197 firewalls resolve cleanly to one of these 8 sites via the spreadsheet's `Assigned Collector` column (RI = sites 2+3 combined at the firewall-routing level, Shea, Vegas, Equinix VA, Dal, Aetna Middletown, Aetna Windsor).

Non-negotiable: no subnet enters an SNA host group without a verified `CANONICAL_LOCATION` in location_master. Update order is **LM → IPAM → SNA configuration**.

## Phase 2 backlog: outlier sites (18 firewalls, 8 distinct sites, currently unmapped)

These sites are **not yet assigned** to one of the 8 Phase 1 environments and are explicitly deferred to Phase 2, not dropped from scope:

**Colo / B2B partner sites** (2 sites, 4 firewalls, FW Type B2B):
- Santa Clara, CA — CoreSite (site code SNC) — 2 firewalls
- Atlanta, GA — QTS (site code ATT) — 2 firewalls

**PSS mail-order / distribution center sites** (3 sites, 6 firewalls, FW Type INTERNAL|PCI): these are CVS mail-order/distribution center locations, not enterprise DCs — internal PCI-scoped firewall pairs.
- Honolulu, HI (site code HOL) — 2 firewalls
- Pittsburgh, PA (site code PIH) — 2 firewalls
- San Antonio, TX (site code STI) — 2 firewalls

**Egress aggregation hubs** (3 site codes, 8 firewalls, FW Type EGRESS) — no Location or Division populated in the source data; physical site vs. logical aggregation point unconfirmed:
- CME-HUB-PROD — 4 firewalls
- CME-HUB-NONPROD — 2 firewalls
- CMC-HUB — 2 firewalls

Total Phase 2 backlog: 8 distinct sites, 18 firewalls (matches the "UNMAPPED" total on the mapping spreadsheet's Summary tab).

**Unresolved from the original vision doc, not yet reconciled against real data:** Wood Dale IL (unplanned 4th CVS DC), Phoenix AZ (Aetna DC), Woodbridge NJ (Aetna DR), and an Atlanta/Sparks NV COLO pairing (The Keep Campus / Switch TRE — distinct from the Atlanta QTS site above) were named in the original architecture doc but do **not** appear anywhere in `netflow_fw_collector_mapping.xlsx`. Do not assume they are in scope, in Phase 2, or dropped — status is open pending confirmation.

## Detection coverage (scored 0–10, at maturity — original 5-domain framing, not yet re-scored per-site)

| Domain (original framing) | Score | Note |
|---|---|---|
| CVS Enterprise | 9.3 | Strong |
| Aetna Enterprise | 9.3 | Strong |
| Retail (SNAT) | 5.2 | Fundamental SNAT constraint, not a deployment quality issue |
| COLO | 7.2 | — |
| Cloud | 8.4 | — |

East-west L7 payload gap applies to *all* sites (no physical taps deployed) — internal DC traffic across Cisco switches is NetFlow metadata only. Mitigations: ISE micro-segmentation, PAN-OS App-ID at firewall insertion points, Cisco XDR endpoint correlation. Primary use cases: healthcare PHI exfiltration detection, ransomware pre-deployment (SMB/RDP spikes, port sweeps, MITRE T1570), encrypted C2 detection via ETA (TLS handshake metadata / cert fingerprinting / beacon timing — no decryption, so no PHI exposure), retail store anomaly detection (RI1-2100 Retail environment, store-aggregate only).

## Identity & integration layer

- **Cisco ISE pxGrid** — real-time user-to-IP binding (802.1X, RADIUS, DHCP). Each independent CSNA environment gets a **domain-scoped pxGrid subscription**; the CVS-side environments must never receive Aetna user-IP mappings and vice versa (cross-domain pxGrid scope = the IP collision problem applied to identity). Not available for the RI1-2100 Retail environment (SNAT masks device identity). Feeds automated ISE quarantine: SNA detection → pxGrid → ISE policy change, in real time, no manual FW rule change (target: <2 min round-trip for the CVS + Aetna enterprise environments).
- **PAN-OS User-ID** — supplements ISE for non-802.1X traffic; App-ID adds L7 context to SNA flows at CVS/Aetna perimeters.
- **ETA (Encrypted Traffic Analytics)** — TLS metadata analysis (cipher suite, cert chain, SNI, timing) without decryption; Talos fingerprinting, beacon detection, DGA detection via DNS flow patterns.
- **Cisco XDR** — cross-environment correlation by entity, not IP; sidesteps the overlap problem entirely at the correlation layer.
- **Splunk** — long-term retention, domain-tagged events, SOC 2 evidence, cross-domain hunt.

## CCD Platform governance (data sources)

- `all_IP_networks v3.78` — 20,942 subnets; `CANONICAL_LOCATION`, `ROUTING_DOMAIN`, `HERITAGE`, `DATA_QUALITY` (Authoritative vs Inferred — drives separate host group tiers). Open patch: Observed→Inferred DATA_QUALITY issue since v3.71, must resolve before CVS enterprise baselining.
- `location_master v5.9g` — 11,526 sites; SITE_CODE, NET_TYPE, HERITAGE, LOCATION_TYPE; source for FC host group naming and retail SITE_CODE mapping.
- `retail_networks v2.8` — 294,341 device records / 9,144 stores; canonical SITE_CODE + metadata only — **device IPs are not SNA-relevant** (SNAT-masked). Store WAN/tunnel IPs come from the 128T controller inventory instead.
- `netflow_fw_collector_mapping.xlsx` — 197-firewall FW-to-Collector dataset; authoritative source for the 8-site Phase 1 model and the Phase 2 backlog above.

## Roadmap

- **Phase 1:** Deploy the 8 independent CSNA environments (Shea, RI1-2100 Corporate, RI1-2100 Retail, EQ-VA, EQ-DAL, Windsor, Middletown, Vegas) — each its own Collector + Flow Broker + Storage. Domain-scoped ISE pxGrid per environment. Validate 0 sampled NetFlow sources; baseline 30 days per environment.
- **Phase 2:** Resolve and onboard the 8 outlier sites (18 firewalls) — Santa Clara, Atlanta QTS (Colo/B2B), Honolulu, Pittsburgh, San Antonio (PSS mail-order/distribution centers), CME-HUB-PROD, CME-HUB-NONPROD, CMC-HUB (egress hubs, location TBD). Confirm whether each attaches to one of the 8 Phase 1 environments or stands up its own.
- **Phase 3 (open):** Reconcile Wood Dale IL, Phoenix AZ, Woodbridge NJ, and the Atlanta/Sparks NV COLO pairing against current data — status not yet determined.
- **Phase 4 (open):** Tuning/maturity — Splunk all environments, ISE quarantine runbooks, SOC 2 evidence mapping, ETA tuning, cross-environment XDR hunt playbooks, annual IPAM/site review, retail baseline maturity review at 90 days post-live.

## Success criteria

**Technical:** 0 cross-environment IP collisions in host groups; 0 sampled NetFlow sources in production; 0 unlabeled Inferred subnets; 0 retail host groups using /26 internal LAN blocks; 0 COLO FCs without ODID validation; config-drift review within 5 business days of any IPAM update.

**Operational (at maturity):** ≥85% detection rate on SOC red-team exercises (CVS + Aetna enterprise environments); <10% false positive rate (90 days post-baseline); <15 min MTTD on simulated lateral movement (CVS enterprise); <2 min ISE quarantine round-trip (CVS + Aetna enterprise); 100% of applicable SOC 2 controls with SNA evidence.

**Compliance:** SNA evidences HIPAA Technical Safeguards (audit controls, auto-logoff monitoring), PCI DSS Req. 10 (log/monitor all access), SOC 2 CC7.2.

## Open prerequisites (must resolve before FC deployment)

**CRIT-1 (hard blocker):** COLO VRF-scoped Flexible NetFlow at LV Switch — configure per-VRF with ODID tagging (`ODID=CVS-VRF`/`ODID=AETNA-VRF`) at all Switch COLO fabric switches; validate before activating the Vegas environment's FC. Without it, CVS and Aetna flows merge.

**CRIT-2 (hard blocker):** RI1-2100 Retail host groups must use store WAN IPs, not internal device IPs — retail is SNAT-masked at the 128T edge; the 294,341 retail_networks device records must **not** be added to the retail host group config.

**CRIT-3 (hard blocker):** Exclude 11 retail /24 collision blocks from CVS/Aetna enterprise host groups — 3 blocks collide with Internal-PBM (172.16.2.0/24, 172.16.7.0/24, 172.20.232.0/24), 8 with Internal-HCB (172.19.5.0/24, 172.19.16.0/24, 172.24.2.0/24, 172.28.1–3.0/24, 172.28.106.0/24, 172.31.224.0/24).

**ATTN-5:** Internet egress FC model ("3 CVS + 2 Aetna egress") needs validation against actual border router topology — IPAM shows only 16 Internet-Facing subnets at RI One + 1 at Phoenix Aetna DC.

**ATTN-6:** GCP BU-tag scoping rules in Cisco Telemetry Broker — 12 confirmed CVS/Aetna IP collisions in GCP space (10.143.x, 10.149.x, 10.236.x); relevant once cloud sourcing is reconciled into the 8-site or Phase 2/3 model.

**ATTN-7:** Reserved address space in production (1.1.1.0 Cloudflare anycast at Shea DC, 203.0.113.0 RFC 5737 TEST-NET at Aetna MDC) — active subnets, do **not** exclude from host groups; flag for IPAM governance remediation instead.

**ATTN-8:** Resolve Observed→Inferred DATA_QUALITY patch (open since all_IP_networks v3.71) before CVS enterprise baselining — ~8,400 subnets carry DATA_QUALITY=Inferred; use distinct naming (`CVS-DC-AUTH` vs `CVS-DC-INFD`) if included before the patch resolves.

## Superseded framing — original five-stack domain model (2026-05-19 vision doc)

The original architecture document organized deployment around 5 logical domain-based "stacks" (Stack 1 CVS Enterprise, Stack 2 Aetna Enterprise, Stack 3 Retail, Stack 4 Common COLO, Stack 5 Cloud) governed by IPAM `ROUTING_DOMAIN`. Michael corrected this (2026-09) against the actual firewall/collector mapping data: **CSNA is deployed per physical site, not per logical domain** — 8 independent environments, each with its own full Collector + Flow Broker + Storage stack, not a shared Manager spanning multiple locations. Rough correspondence for orientation only (do not treat as authoritative — the 8-site model above is authoritative):

- Stack 1 (CVS Enterprise) ≈ Shea + RI1-2100 Corporate (Wood Dale IL and internet egress FC placement from the original doc unconfirmed against current data)
- Stack 2 (Aetna Enterprise) ≈ Windsor + Middletown (Phoenix AZ, Woodbridge NJ unconfirmed)
- Stack 3 (Retail) ≈ RI1-2100 Retail
- Stack 4 (COLO) ≈ Vegas, plus EQ-VA/EQ-DAL as newly-identified independent COLO environments not named in the original doc at all (Atlanta/Sparks NV from the original doc unconfirmed)
- Stack 5 (Cloud) — not represented in the 8-site model; status open, see ATTN-6

The `ROUTING_DOMAIN`-derived host-group governance logic (LM → IPAM → SNA, Authoritative/Inferred tiering, CANONICAL_LOCATION requirement) still applies within each of the 8 site environments — only the site/environment grouping changed, not the host-group derivation rules.

## Working notes

- "SNA" here = **Secure Network Analytics** (NDR/behavioral). Don't conflate with "Secure Network Access" (NAC) — that's a different Cisco product line covered by nac-ztna-fpms / forescout-hw-refresh.
- The 8-site model and Phase 2 backlog are current as of 2026-09-01, cross-referenced against `netflow_fw_collector_mapping.xlsx`. Treat counts (firewalls, subnets) as this snapshot's figures; re-validate if a newer version of that spreadsheet or IPAM/LM is referenced.
- "PSS" and "PCW" are CVS Health division codes seen in the FW mapping spreadsheet (PSS = 108 firewalls, PCW = 52, Colo = 13, Aetna = 2) — PSS sites include the Honolulu/Pittsburgh/San Antonio mail-order/distribution centers; full definitions of both codes not yet confirmed.
- When asked about FC/environment placement for a specific subnet or firewall, use the 8-site table and Phase 2 backlog above rather than the superseded ROUTING_DOMAIN-to-stack mapping — consult fw-src-dst-policy-analysis's directionality/topology-fingerprint method if the question also involves firewall enforcement, not just SNA visibility.
