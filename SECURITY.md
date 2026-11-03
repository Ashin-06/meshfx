# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately, through GitHub's private vulnerability
reporting on this repository (Security → Report a vulnerability) or by contacting the
maintainer, [@Ashin-06](https://github.com/Ashin-06), directly. Do not open a public issue.

Include what you found, how to reproduce it and what an attacker could do with it. You should
get an acknowledgement within 5 working days. Please give us 90 days to fix an issue before
disclosing it, and don't test against anyone else's deployment.

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | yes |
| < 1.0 | no (research prototype releases) |

## Scope

In scope: the ESP32 partition table and LittleFS extraction, the protobuf and transmit-history
decoders, message parsing and carving, the companion-app database readers, the timeline and
reports, the analysis API and its log, the container image and the CI configuration. A crafted
flash dump or database that crashes the parser, exhausts memory, writes outside the output folder,
runs code through SQLite, or changes what the timeline attributes is in scope.

Out of scope: decrypting captured traffic, nRF52 LittleFS v1 (not supported yet), and findings that
need an already-compromised host or a leaked API key.

This project has **not** had an independent security review or penetration test, and its
methods have not been validated in court.
