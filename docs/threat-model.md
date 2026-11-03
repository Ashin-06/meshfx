# Threat model

What the analysis service protects, from whom, and what is still open. Written for the 1.0.0 code;
nobody independent has reviewed it.

## What it protects

| Asset | Where it lives |
|---|---|
| Timelines and attribution that may be cited in a case | API responses and the `analyses` table |
| Submitted evidence (flash dumps, companion-app databases, raw images) | request bodies and, for databases, a temporary file removed after each request; never stored |
| API keys | callers hold the key; the service holds only SHA-256 hashes |

Mesh radios are used by protesters and rescue teams as well as criminals: a leak of who talked to
whom can endanger people. A wrong attribution can implicate the wrong person.

## Trust boundaries

1. **Examiner → service.** Flash dumps and databases come from seized devices and may be crafted to
   break forensic tools.
2. **CLI → examiner's disk.** `extract` writes files whose names come from the seized image.

## Threats and what stops them

| Threat | Mitigation | Residual risk |
|---|---|---|
| A crafted image writes outside the output folder | `extract` resolves every path and refuses any outside the chosen folder | — |
| A crafted database runs code or writes through SQLite | Opened read-only and immutable with `trusted_schema = OFF`; schema-supplied column names are quoted as identifiers | SQLite parser bugs |
| A corrupt flash dump crashes or hangs the parser | Any parser failure becomes a 422; 40 MB body cap | LittleFS is mounted by `littlefs-python`, a C extension |
| Over-reading attribution | The report grades each message (signed, PKI-encrypted, channel-only) and never claims more than the stored flags show | Signatures are not re-verified |
| Someone reads the log or submits evidence | API keys with roles; no CORS unless listed | Every `viewer` sees every analysis |
| Evidence leaks through errors or logs | Validation errors don't echo input; unhandled errors return only a request ID | — |
| A result is disputed later | The log keeps the input's SHA-256; the flash response lists every file with its SHA-256 | The log is not signed or hash-chained |

## Not covered

- Acquisition: imaging the radio's flash is a hardware step (see research/04).
- nRF52 LittleFS v1 extraction.
- TLS (terminate it at the ingress).
