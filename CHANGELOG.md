# Changelog

Public releases use a `-public.N` suffix so they are distinguishable from inherited application and model version labels.

## v2.1.3-public.1 — 2026-10-23

First documented public source preview of Football Data Service.

### Added

- Chinese and English project overview, verified configuration paths, architecture and setup guides.
- Credential-free offline example calling the existing feature extractor, scoring model, threshold filter and result validator; synthetic fixtures, HTML report and JSON output.
- Explicitly selected offline pytest suite, CI matrix, Python syntax checks and tracked-file secret scanning.
- Contribution / security guidance, maintainer and provenance record, issue and PR templates, roadmap and release notes.

### Fixed

- Quick-start login configuration destination: the collector reads the root `config.json`.
- Ignore rules for root credential files and generated demo / check artifacts.
- Removed a token-shaped placeholder from Telegram setup guidance to keep strict credential scans unambiguous.
- Enforced UTF-8 for cross-platform scanning and emptied legacy OCR placeholders detected by the Linux checks.
- Bounded ASCII / Chinese text generation in feature property tests to avoid expensive cold-start Unicode strategy initialization.

### Verification scope

Core offline behavior and source publishing checks only. The full application dependency environment, online collection, real notifications and historical performance remain unvalidated in this public preview. No binary installer or bundled dataset is provided.

## Initial sanitized source — 2026-10-23

- Exported selected source and documentation from the existing private project into a new public Git history.
- Removed embedded credentials and runtime data, added empty configuration examples, ignore rules and MIT license.
- Repaired two inherited Python syntax errors during the initial source check.
