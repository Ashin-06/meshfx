# 09 · Paper Plan

## Target venues (pick by timing)

| Venue | Fit | Note |
|---|---|---|
| **DFRWS USA / EU** (proceedings in *FSI: Digital Investigation*) | best: the Ray-Ban Meta glasses paper is the template | check this year's CFP deadlines |
| *Forensic Science International: Digital Investigation* (journal) | extended version with MeshCore/Reticulum | rolling |
| ARES (IWCC / COSH workshops) | shorter, faster | |
| Tool track / OSDFCon / SANS DFIR Summit talk | tool release | good for visibility |

## Working title
**"What the Mesh Remembers: Forensic Analysis of Meshtastic LoRa Mesh Radios and Their Companion Apps"**

## Outline

1. **Introduction**: off-grid LoRa mesh adoption (protest logistics, SAR, outdoor); the evidence gap; contributions
2. **Background**: Meshtastic architecture, LoRa PHY, packet format, crypto (CTR channels, PKI DMs, XEdDSA 2.8.1+), firmware lineage
3. **Related work**: IoT/embedded forensics, wearable + companion-app frameworks (Ray-Ban Meta), messaging-app forensics, the CTF write-ups, offensive Meshtastic research (DEF CON 34)
4. **Methodology**: devices, firmware versions, scenario, ground truth, acquisition methods, anti-forensic matrix, ethics
5. **Evidence map**: radio flash (all files and binary formats), raw regions (warm ring), Android/iOS stores, MQTT, RF
6. **Acquisition**: per-chip SOPs, order of volatility (2 h RAM window, write-behind cache), validated non-invasiveness
7. **Results**
   - 7.1 survival matrix (actions × artifacts × platform)
   - 7.2 deleted-data recovery (carving: ESP32 vs nRF52 lfs v1)
   - 7.3 what factory reset leaves behind
   - 7.4 phone apps: per-radio databases, LRU deletion, drafts, WAL/FTS remnants
   - 7.5 timestamps: boot-relative records and anchoring
8. **Attribution**: confidence levels A–D, forgery demonstration, key-change evidence
9. **Tool**: MeshFX design, validation results, ALEAPP/iLEAPP plugin
10. **Discussion**: version churn (2.8 format break), lockdown builds, limits, guidance for investigators **and for users**
11. **Conclusion and future work**: MeshCore, Reticulum, multi-receiver localisation

## Contributions (claim list)
1. The first forensic evidence map of Meshtastic across radio, apps, MQTT and RF.
2. Validated, non-invasive acquisition procedures for ESP32, nRF52840 and RP2040 nodes, with an order of volatility.
3. An anti-forensics study showing what survives deletion and factory reset.
4. An attribution-confidence framework for mesh messages.
5. MeshFX (open source) and a synthetic reference dataset.

## Artifacts to release
- `meshfx` (MIT / Apache-2.0)
- reference images and app extractions (synthetic personas only) with SHA-256 manifest and ground-truth logs
- ALEAPP / iLEAPP plugin PRs
- "What your radio remembers": a one-page guide for Meshtastic users
