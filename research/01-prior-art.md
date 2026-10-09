# 01 · Prior Art and the Gap

Searched 9 Oct 2026. Sources: web search (standard + extended), GitHub, arXiv, DFRWS, IEEE S&P 2026 posters, Forensic Focus, DEF CON 34 schedule.

## Searches run

| Query (abridged) | Result |
|---|---|
| Meshtastic forensics device acquisition message recovery | nothing forensic; only Meshtastic docs and a generic IM-forensics paper |
| "Meshtastic" forensic analysis paper node database flash extraction | nothing; generic flash-forensics papers only |
| MeshCore / Reticulum forensic analysis | nothing; protocol overviews only |
| github meshtastic flash dump littlefs extract prefs | two **CTF write-ups** (below) and littlefs tooling |
| Meshtastic security research DEF CON 2025/2026 | offensive work and CVEs (below) |
| Meshtastic SDR GNU Radio decode | RF tooling (below) |

## Closest work, and how MeshFX differs

### 1. RealWorldCTF 2024, "Long Range 2" (Jan 2024)
Write-ups: [nanax](https://blog.nanax.fr/post/2024-01-28-hardware-longrange2/), [sec.gd](https://sec.gd/blog/en/posts/long-distance-2/)

What they did:
- took an 8 MB flash dump of a T-Beam S3 and found the partition table at `0x8000`
- found the `spiffs` partition at `0x300000` and read it as LittleFS
- extracted `db.proto`, `config.proto` and `channels.proto`, then decoded them with `protoc`
- pulled the channel key and demodulated a recorded LoRa capture with gr-lora
- decrypted with AES-CTR to recover the flag

What it proves: the basic idea works on ESP32.

What it does **not** cover, and MeshFX does:
- the current file layout (2.6+ splits `device.proto` and `nodes.proto`; 2.7/2.8 add `Messages_*.msgs`, `warm.dat`, `transmit_history.dat`, `/backups`)
- nRF52 (LittleFS **v1**, 128-byte blocks, raw warm ring outside the filesystem)
- deleted-data recovery
- the effects of reset and factory reset
- phone-app artifacts
- PKI direct messages
- attribution reliability
- order of volatility
- a repeatable method or a validated tool

### 2. DEF CON 34 Ham Radio Village, "Meshtastic Beasts and Where to Find Them" (8 Aug 2026)
Speakers: Jon Marler (K4CHN), Scott Thompson (KF5CPY). [Abstract](https://cfp.hamvillage.org/dc34/talk/CTMAYM/)

Offensive only: forgery/impersonation, eavesdropping on cleartext headers, packet sabotage, node-DB exhaustion. There is no forensics content.

Relevant to us: it shows **why attribution needs confidence scoring** (see [05](05-rf-mqtt-attribution.md)).

### 3. CVEs and advisories

| ID | Issue | Forensic relevance |
|---|---|---|
| [CVE-2025-52464](https://www.tenable.com/cve/CVE-2025-52464) | duplicated / low-entropy keypairs, 2.5.0–2.6.10 | the same private key may sit on many devices, so a key is not a unique identity on affected versions |
| [CVE-2025-21608](https://nvd.nist.gov/vuln/detail/CVE-2025-21608) | forged DMs via MQTT, ≤2.5.18 | "DM from X" in an app database may be forged |
| [GHSA-h4rg-g6f3-ghh7](https://github.com/meshtastic/Meshtastic-Android/security/advisories/GHSA-h4rg-g6f3-ghh7) | forged DMs without PKC shown as encrypted (Android) | the app's encrypted-message UI is not proof |
| [DEF CON 2025 blog](https://meshtastic.org/blog/that-one-time-at-defcon/) | spoofed NodeInfo overwrote the local node's own names | node names in `nodes.proto` can be attacker-written |

### 4. RF tooling (capture, not forensics)
- [Meshtastic_SDR](https://gitlab.com/crankylinuxuser/meshtastic_sdr) (Josh Conway): GNU Radio RX/TX flowgraphs plus a Python decoder
- [gr-lora_sdr](https://github.com/tapparelj/gr-lora_sdr) (EPFL): LoRa PHY
- [Jeff Geerling, 2025](https://www.jeffgeerling.com/blog/2025/decoding-meshtastic-gnuradio-on-raspberry-pi/) and [RTL-SDR.com](https://www.rtl-sdr.com/decoding-meshtastic-in-realtime-with-an-rtl-sdr-and-gnu-radio/): how-tos

We reuse these for capture. MeshFX adds evidence handling: hashing, timestamps, linking captures to device artifacts, attribution scoring.

### 5. Adjacent forensic methodology to copy
- [Ray-Ban Meta glasses, DFRWS USA 2026](https://dfrws.org/presentation/seeing-the-evidence-a-forensic-framework-for-analyzing-ray-ban-meta-ai-smart-glasses/) (Panta, Alsmadi, Baggili): device + companion app + cloud, anti-forensic tests, ALEAPP plugin. **Same paper shape as ours.**
- [Nyon Unchained, Bosch eBike computers (arXiv 2404.12864)](https://arxiv.org/pdf/2404.12864): embedded-device forensic acquisition
- [Zenbo humanoid robot forensics](https://zuscholars.zu.ac.ae/works/6716): IoT device as a "witness"
- [Systematic firmware extraction for industrial embedded devices (FSI:DI 2026)](https://www.sciencedirect.com/science/article/pii/S2665910726000447): extraction taxonomy to cite

## Gap statement (for the paper)

> Off-grid LoRa mesh messengers are widely used for protest logistics, disaster response and outdoor safety, and they hold message history, contact lists, location traces and long-lived cryptographic identities. No published work documents their forensic artifacts, acquisition methods, deletion behaviour or the reliability of sender attribution. We present the first forensic analysis of Meshtastic across radio, companion apps and the RF/MQTT layers, plus an open-source tool and reference dataset.

## Risk that someone publishes first

The topic is open but obvious, and DFRWS-style groups are actively covering new device classes.

Mitigation:
- post a preprint or tool release early (phase 3)
- re-run these searches monthly: Google Scholar alert on `Meshtastic forensic`, arXiv `cs.CR` keyword alert, DFRWS programs
