# coverage-cache/

Incremental JaCoCo cache. Binary `.exec` files plus per-class summaries.

| File              | Purpose                                                 |
|-------------------|---------------------------------------------------------|
| `baseline.exec`   | Snapshot from the last green full cycle (read-only).    |
| `<fqcn>.exec`     | Per-class merged exec file, updated atomically.         |
| `<fqcn>.json`     | Per-class JSON summary (line/branch/instr/complexity).  |
| `index.json`      | `{ fqcn -> sha256, lastUpdated, baselineHash }`         |

See `skills/11-coverage/coverage-cache.md` for the update protocol, invalidation
rules, and baseline-refresh policy. Agents never read `.exec` directly — they
consume `state/coverage-delta.json` and `state/coverage-summary.json`.
