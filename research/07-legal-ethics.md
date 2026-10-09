# 07 · Legal and Ethical Ground Rules

This is not legal advice. Get sign-off from your supervisor or institution (and an ethics board if your university requires one for security research) before the RF/MQTT parts.

## Lab rules (non-negotiable)

1. **Only our own devices.** Every radio and phone in the lab is bought for the project and listed in `lab/inventory` with serial numbers.
2. **A private channel with a random 256-bit PSK and a non-default name** for all scenario traffic. Do not run experiments on the default `LongFast` / `AQ==` channel, where strangers' packets would mix in.
3. **MQTT uplink off** on lab radios, so lab traffic never reaches public brokers or maps. If the MQTT study needs a broker, run a local Mosquitto.
4. **RF captures:** filter to our own node IDs before storing decoded content. Delete any third-party frames. Never try to decrypt third-party traffic.
5. **Transmit within ISM rules**: region set correctly, duty-cycle and power limits respected (Meshtastic enforces region limits; do not override them).
6. **Published dataset = synthetic only**: lab devices, scripted messages, fake names, positions jittered or at a public test site.

## Law: the questions to check in your jurisdiction

| Question | Why it matters | Examples |
|---|---|---|
| Is receiving unencrypted radio traffic lawful? | passive header capture | US: 18 U.S.C. §2511 has an exception for "readily accessible" radio; many countries are similar, some are stricter |
| Is decrypting or using intercepted encrypted content lawful? | the decrypt features | usually needs a warrant or interception order; a researcher must not do it to others' traffic |
| Device examination authority | casework use of the SOPs | a warrant or consent covering the radio *and* phone *and* any cloud/MQTT account |
| Personal data | node names, positions and messages are personal data | GDPR (EU/UK), DPDP Act 2023 (India), etc. Minimise, secure and delete. |
| Spectrum licensing | transmitting | e.g. EU868 1% duty cycle; IN865 865–867 MHz licence-exempt in India; US915 under FCC Part 15 |

## Dual-use and responsible disclosure

- **Who benefits:** investigators *and* users. Activists and disaster teams rely on Meshtastic. Many of our findings are things users should know:
  - factory reset does not erase `/backups`
  - messages survive in flash
  - the default key is public
  - names can be forged

  Publish a **user-facing "what your radio remembers" guide** alongside the paper.
- **Tool scope:** decrypt only with keys supplied by the examiner. No key cracking, no jamming, no transmit or forgery features in the public tool. The lab forgery test (L7) stays in a private script.
- **Disclosure:** report anything that is a vulnerability rather than a design property (e.g. keys left behind after "erase") privately to Meshtastic first (repo `SECURITY.md` / GitHub security advisories). Allow a reasonable fix window before publishing.
- Do not publish acquisition bypasses for **lockdown** builds (APPROTECT glitching). Describe them at a high level only.

## Evidence-handling standards to cite
- ISO/IEC 27037 (identification, collection, acquisition, preservation)
- NIST SP 800-86 (forensic techniques in incident response)
- SWGDE best practices for embedded / IoT device acquisition
- ACPO principles (UK): change as little as possible; document every change (see the clean-shutdown decision in [04](04-acquisition.md))
