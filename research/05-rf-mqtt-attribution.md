# 05 · RF Capture, MQTT and Attribution

## 1. Passive RF capture

**Setup:** an RTL-SDR Blog V4 (or HackRF / USRP) feeding GNU Radio with [gr-lora_sdr](https://github.com/tapparelj/gr-lora_sdr) and [Meshtastic_SDR](https://gitlab.com/crankylinuxuser/meshtastic_sdr).

**Parameters:**
- region band, preset (LongFast: BW 250 kHz, SF11, CR 4/5), sync word `0x2B`
- the frequency slot is `djb2(channel name) % numSlots` unless overridden ([02 §4](02-meshtastic-internals.md#4-radio-layer)), so the channel name from a seized radio tells you which slot to monitor

**Evidence handling:**
- keep the **raw IQ** as well as the decoded frames
- hash both
- timestamp from a GPS-disciplined or NTP-synced host
- log the receiver location, antenna and gain

Decoded frames are a derived product. The IQ file is the evidence.

### Without any key, the cleartext header gives:
- `from`, `to`, `packet id` → **who talks to whom, how often** (traffic analysis)
- `hop_start − hop_limit` → hops travelled; `relay_node` / `next_hop` → which relays carried it
- `channel hash` → which channel. Test candidate (name, key) pairs offline: the defaults (`AQ==` with every preset name) match many public meshes immediately
- RSSI/SNR/time of arrival; with ≥3 synchronised receivers, transmitter **localisation** (research extension)

### With keys:
- **Channel traffic:** `meshfx.py decrypt <hex> --psk <base64>`
- **PKI DMs:** a seized radio's `config.proto` private key decrypts **every captured DM to or from that node, including old ones**, because there is no forward secrecy. Use `meshfx.py decrypt-pki`.
- **AEAD channels (2.8.1+):** to implement once the CCM nonce layout is documented from `encryptPacketCCM`

## 2. MQTT

- A gateway node uploads packets to `msh/<REGION>/2/e/<CHANNEL>/!<gateway>` as a `ServiceEnvelope` (packet + channel id + gateway id). It stays encrypted if the channel has `encryption_enabled`.
- **Sources:**
  - the broker operator (legal process)
  - a passive subscription to public topics (legal review first, see [07](07-legal-ethics.md))
  - map aggregators (node info and coarse position)
- `module.proto` on a seized radio names the **broker and credentials** it used. That links the radio to a server account.
- `via_mqtt` (header bit 4, and the `via_mqtt` column in the Android `nodes` table) marks traffic that crossed the internet. **A node "heard" over MQTT may be on another continent.**

## 3. How far to trust "from": attribution confidence

The examiner must not report "X sent this message" without qualification. The tool will put one of these levels on every message:

| Level | Condition | Why |
|---|---|---|
| **A: Strong** | XEdDSA signature verified (`xeddsaSigned=1` on 2.8.1+, or re-verified by us with the sender's public key) **and** the key is not on the known-compromised list | only the private-key holder can sign; covers from/id/to and the whole `Data` |
| **B: Pairwise** | PKI DM whose CCM tag verifies with the key pair | proves it came from one of the two key holders; plus the key-uniqueness check |
| **C: Channel** | channel message, private PSK | anyone holding the PSK can forge `from` (no integrity in CTR) |
| **D: Weak** | default/public key (`AQ==`), or via MQTT on ≤2.5.18 (CVE-2025-21608), or an affected-key version (CVE-2025-52464: 2.5.0–2.6.10), or an app flagged by GHSA-h4rg-g6f3-ghh7 | forgery is trivial or documented |
| Name only | sender shown only by long/short name | names are self-asserted and can be overwritten by spoofed NodeInfo |

Extra checks:
- `nodes.key_match` / `new_public_key` (Android) record **public-key changes** for a NodeNum. That signals either a re-keyed device or impersonation.
- Firmware 2.6.12+ contains a list of known-compromised keys. Reuse it to flag keys.
- On 2.8+ NodeNum = CRC-32(public key), so a NodeNum that does not match its key is suspicious.

## 4. Location evidence: what it can and cannot show

| Signal | Meaning | Caveat |
|---|---|---|
| node position (lat/lon) | self-reported by that node | spoofable; `fixed_position` may be typed in by hand; `precision_bits` < 32 means a deliberately coarse grid, so report it as an area |
| `hops_away = 0` / direct SNR/RSSI | heard directly on RF | LoRa reaches 1–10+ km, much more from high sites, so "direct" ≠ "beside" |
| `via_mqtt` | heard over the internet | says nothing about physical proximity |
| range test CSV | sender positions plus SNR at this receiver | best "this device was within RF range of that position at time T" evidence |
| Android `discovery_session.user_latitude/longitude` | **the phone's own** GPS fix during a scan | strong for the phone's location |

## 5. Lab tasks from this file
- **L1**: capture own-device traffic with an RTL-SDR and decrypt it with meshfx. This is the first live check of the channel-decrypt path.
- **L6**: build a candidate channel-hash dictionary (presets × default-key indices 1–10).
- **L7**: forge a channel message in the lab (own devices) and show that the stored artifacts look identical to a genuine one, so the attribution levels matter.
