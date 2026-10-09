# 06 · Phase 2 Targets: MeshCore and Reticulum

These are the other two off-grid LoRa mesh stacks. No forensic work was found for either (searched 9 Oct 2026). Extend MeshFX to them after Meshtastic is done. The same parser architecture applies.

## MeshCore (`meshcore-dev/MeshCore`)

A lightweight C++ mesh with source-routed paths, and separate firmware roles: **companion radio**, **repeater**, **room server**.

Companion-radio files (from `examples/companion_radio/DataStore.cpp`, read 9 Oct 2026):

| Path | Content | Forensic value |
|---|---|---|
| `/_main.id` (or `/identity/…` on some platforms) | node identity (Ed25519 key material) | identity; decrypt or attribute |
| `/new_prefs` (legacy binary), `/prefs.json` | node preferences | name, radio settings |
| `/contacts3` | fixed records: `pub_key[32], name[32], type, flags, pad, sync_since(4), out_path_len, last_advert_timestamp(4), out_path[64], lastmod(4), gps_lat(4), gps_lon(4)` | **every contact with last advert time and GPS position**, plus **routing path (which repeaters)** |
| `/channels2` | `pad[4], name[32], secret[32]` | channel keys |
| `/adv_blobs` (nRF52/STM32), `/bl/` (ESP32/RP2040) | advert blob cache | which nodes advertised |

- **No message history on the companion radio.** Messages live in the phone app.
- 🧪 **Room servers** store posts for clients (BBS-style). That could be the richest MeshCore artifact; analyse the room-server firmware's storage.
- Phone app: the official MeshCore app (Flutter). 🧪 Storage location and format still to be researched.

## Reticulum (RNS) + LXMF

A Python network stack, transport-agnostic (LoRa via RNode, TCP, I2P, …). Messaging uses **LXMF**. Clients: **Sideband** (Android/desktop), **NomadNet** (terminal), **MeshChat** (desktop/web).

The radio (RNode) is just a modem: expect almost nothing on it. **All evidence is on the host.**

| Location (🧪 verify against RNS/LXMF source) | Expected content |
|---|---|
| `~/.reticulum/config` | interfaces (LoRa frequency/SF/BW, TCP peers, I2P) → **which networks** |
| `~/.reticulum/storage/identities`, transport identity | keys |
| `~/.reticulum/storage/known_destinations` | destination hash → public key, **last-seen time**, app data (names) |
| LXMF router store (`~/.lxmf/`, or the app's own directory) | queued and propagated messages |
| Sideband / NomadNet / MeshChat app data | **message database**, contacts, telemetry/locations (Sideband shares location) |

## Plan
1. Repeat the Meshtastic method: evidence map → acquisition → deletion tests → parser.
2. Common output schema across the three stacks (node, message, position, key, observation) so one timeline can mix them.
3. Short paper or extended journal version: "Forensics of off-grid LoRa mesh messengers: Meshtastic, MeshCore and Reticulum".
