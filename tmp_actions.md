# Routine Score Parser — Analysis and Actions

Source of truth for the narrative: `Logs to build dashboard.md` → `2026-10-02 loading routin's score error` (lines 13–235).

Status: **diagnosis complete, arithmetic verified, no code changed yet.**
Analysis date: 2026-10-02.

---

## TL;DR

The parser reads **five** judge columns as **four**. As a result **not one of the 63 scoring
rows** in `AG 12U Female Solo Details.pdf` is read correctly: 41 are dropped with a warning and
22 are silently stored wrong. The run still printed `[OK]` and committed understated scores.

Across the whole meet, only **181 of 1818** scoring rows (10%) are read correctly. All 17
detailed PDFs are affected.

Separately: **six live tenant API keys were pasted into `Logs to build dashboard.md`.** They
have been redacted in place but must still be rotated.

---

## Root cause — three defects

### 1. Four judge slots, five judges

The sheet header is:

```
Code Rank Draw Swimmer Ref DD J1 J2 J3 J4 J5 Total Pen. Total Routine
```

Confirmed positionally on page 1: the `J1`…`J5` columns each hold a value on **all 21**
scoring rows, while `DD` holds one on only **12** of them.

`scripts/ingest_routines.py:237` and `:266` capture `j1..j4` with no slot for `J5`. On every row
that *did* match, **J5 was stored as the line total**. No warning fires for this.

### 2. Trailing columns are hardcoded

| Regex | Accepts trailing numbers |
|---|---|
| `el_match` (`:237`) | exactly 0 or 2 |
| `ai_match` (`:266`) | exactly 0 or 1 |

Real rows carry 1, 2 or 3 depending on position, so the count cannot be fixed by loosening the
pattern. The first row of each panel carries the cumulative; the first element row also carries
the routine score.

### 3. The deduction column is invisible to whitespace parsing

This is the subtle one. Measured x-positions:

| Column | x0 |
|---|---|
| Ref | 195.4 |
| DD | 214.6 |
| J1 | 243.4 |
| J2 | 267.3 |
| J3 | 291.3 |
| J4 | 315.2 |
| J5 | 339.2 |
| Total (line) | 372.7 |
| Pen. | 401.5 |
| Total (cumulative) | 439.8 |
| Routine | 502.2 |

On an ordinary row the `Ref` cell is empty. On a deduction row **both are filled** — `Ref` holds
the original difficulty, `DD` holds the awarded difficulty:

```
HYBRID (0.5) 7.000 0.500 6.25 6.00 6.25 6.00 5.50 1.5208
            x=195 x=215 x=243 ...
```

Read as text that is just an extra number in slot two, indistinguishable from a judge score.
All 4 deduction rows therefore *matched*, and the parser read `0.500` as `J1`. That is how
MERAQUAS OF IRVINE ended up with `element_total = 5.5` and `routine_score = 1.5208`.

`element_total` is **assigned, not summed** (`:249`), so it only ever holds whichever row
matched last.

---

## The 41 dropped lines

Each athlete loses the same five rows: all four element rows plus its **first** AI row.

| Count | Shape | Why it fails |
|---|---|---|
| 23 | `DD J1..J5 line_total` | Regex takes DD + J1..J4 + `total`, consuming J5 as the total. One number left, but the trailing group needs **two** → rejected |
| 18 | `DD J1..J5 line_total cum_total routine` | Maps `cum_total`→`routine`, then `161.0500` unconsumed → `$` rejects |
| 9 | AI `J1..J5 line_total cum_total` | AI regex allows only **one** trailing number → rejected |

23 + 18 = **41**, reproducing the warning exactly.

The 22 rows that *did* match are all wrong:

- 18 plain AI rows — J5 stored as the line total.
- 4 deduction rows — see defect 3.

> The warning text looks truncated because `:308` stores `current.strip()[:80]`. The real line
> does carry `161.0500`. The full 41-line dump was produced during analysis; reproduce it with
> the script in *Verification* below.

---

## Correct arithmetic — proven on all 63 rows

Recomputing every scoring row from the judge values and comparing against the printed line
totals gave **zero mismatches**.

```
element line total = mean of the middle three of J1..J5  x  awarded DD  /  2
AI line total      = mean of the middle three of J1..J5  x  factor  x  3
DD used            = the AWARDED value in the DD column, NOT the Ref value
printed Total      = sum of the four element line totals
printed AI Total   = sum of the three AI line totals
printed Routine    = elements Total + AI Total
```

Worked examples:

- First row — sorted `5.50 6.25 6.50 6.50 6.50`, trim to `6.50 6.50 6.25`, mean `6.41667`,
  `x 7.000 / 2 = 22.4583`. Matches the sheet.
- Deduction row — sorted `5.50 6.00 6.00 6.25 6.25`, trim to `6.00 6.00 6.25`, mean `6.08333`,
  `x 0.500 / 2 = 1.5208`. Confirms the awarded DD scores the element, and that
  `TOTAL DIFFICULTY 21.500 28.000` is `7+7+7+0.5` against `7+7+7+7`.

All nine athletes reconcile against their own printed totals — elements, AI, and routine.

---

## What the database holds right now

Nine rows were written to `as_meet_routine_result`. Eight of nine routine scores are
understated, six are recorded as `0.00`, and the two non-zero rows are non-zero for the wrong
reason.

| Club | element_total now / truth | AI total now / truth | routine now / truth |
|---|---|---|---|
| ARMADA | 0.00 / **85.75** | 26.25 / **75.30** | 0.00 / **161.05** |
| SAN FRANCISCO | 0.00 / **84.24** | 25.20 / **73.00** | 0.00 / **157.24** |
| SOUTHERN NEVADA | 0.00 / **76.99** | 24.85 / **71.70** | 0.00 / **148.69** |
| SEATTLE SYNCHRO | 0.00 / **76.82** | 23.45 / **68.05** | 0.00 / **144.87** |
| MERAQUAS | 5.50 / **66.85** | 24.50 / **71.60** | 1.52 / **138.45** |
| SEATTLE SYNCHRO | 4.75 / **52.95** | 23.80 / **67.95** | 1.29 / **120.90** |
| SAN DIEGUITO | 5.00 / **30.87** | 23.10 / **66.35** | 1.21 / **97.22** |
| SAN DIEGO SEA STARS | 0.00 / **19.29** | 23.10 / **67.25** | 0.00 / **86.54** |
| SAN DIEGO SEA STARS | 4.75 / **11.94** | 22.05 / **63.30** | 1.23 / **75.24** |

---

## Blast radius

The real regexes applied to every scoring row in all 17 detailed PDFs, each capture checked
against positional truth:

| Metric | Count |
|---|---|
| scoring rows read correctly | **181 / 1818** (10%) |
| silently mis-parsed | **370** |
| dropped with a warning | **928** |

By category:

| Category | Rows | Correct | Wrong | Dropped |
|---|---|---|---|---|
| Element | 894 | 117 | 46 | 731 |
| AI | 573 | 64 | 324 | 185 |
| STC | 351 | — | — | 12 dropped |

Notes:

- The ~181 "correct" rows are ones where J5 happened to equal the value the parser put in the
  total field. Coincidence, not correctness.
- 43 deduction rows exist across the meet; every one is mis-parsed.
- **STC is a separate code path (`:283`) and is NOT verified.** 339 of its 351 rows match its
  own regex, but the column semantics were not established. Do not assume they are right.
- The `synchronization_total is NULL` warning is a **false alarm for solo PDFs** — solo routines
  have no STC section; STC rows appear only in duet and team PDFs. It is emitted
  unconditionally at `:326`.

---

## Actions

### P0 — security

- [ ] **Rotate the six exposed tenant API keys.** They were pasted into
      `Logs to build dashboard.md` and into terminal scrollback. Only bcrypt hashes are stored
      in the database, so they cannot be recovered. Affected tenants: ARMADA ARTISTIC SWIM
      TEAM, SAN FRANCISCO MERIONETTES, SOUTHERN NEVADA DESERT MERMAIDS, MERAQUAS OF IRVINE,
      SAN DIEGUITO SEA DRAGONS, SAN DIEGO SEA STARS.
      *(Already done: the six values in the log were replaced with `[REDACTED-ROTATE]`, club and
      tenant id retained. 0 live-format keys remain in the file. Rotation is still required.)*
- [ ] **Stop printing secrets to stdout.** `synchronized_meet` in
      `scripts/user_mgmt_sync.py` prints the full key, which is exactly what a log capture or CI
      job keeps. Add a flag that suppresses the value and prints only the prefix.

### P0 — data integrity

- [ ] **Remove the 9 bad `as_meet_routine_result` rows** before any corrected re-import. Find them
      by source path
      `swim-meets\2026\20260305_WestZone_Sacramento_CA\AG 12U Female Solo Details.pdf` under the
      event/meet created by this run. Note the six clubs and their tenants were created by the
      same run — decide whether to keep them.
- [ ] **Do not re-import until the parser is fixed**, otherwise `--replace-source` will rewrite
      the same understated numbers.

### P1 — parser fix

- [ ] **Parse by column position, not whitespace tokens.** Detect the header row per page and
      record the x position of every label. Do **not** hardcode the x values in the table above —
      the duet and team sheets are laid out differently.
- [ ] **Accept five judges.** Add `j5`; drop the hardcoded trailing counts; read `cum_total` and
      `routine` from whichever columns are present on that row.
- [ ] **Treat `Ref` as the optional nominal DD** and `DD` as the awarded value that actually
      scores the element.
- [ ] **Rename the two `Total` columns** in the code so `line_total`, `cum_total` and `routine`
      cannot be confused again.
- [ ] **Validate before writing.** Recompute each line total from the judges, recompute the panel
      totals and the routine score, and refuse any row that does not reconcile — naming the row
      rather than storing a number from the wrong column.
- [ ] **Make a dropped scoring row fatal.** A parse failure that changes official scores must not
      be able to print `[OK]`, and should roll back the whole import. This is the constitution's
      data-integrity and no-overwrite rule (Principles 4 and 11).

### P1 — tests

- [ ] **Fold the analysis into real regression tests**; the throwaway scripts used during analysis
      live in `%LOCALAPPDATA%\Temp\opencode\` (`analyze_routine.py`, `columns_routine.py`,
      `cols_page2.py`, `verify_routine.py`, `verify2.py`, `blast_radius.py`, `dump41.py`) and must
      not be relied on.
- [ ] Cover: 5-judge rows, 8/9/10-token element rows, AI first vs later rows, deduction rows,
      first-row cumulative and routine columns, and the arithmetic formulas above.
- [ ] Add a guard test asserting the parser never emits a non-reconciling score.
- [ ] `pytest` is unavailable. Use `python -m unittest discover -s tests -t .` — currently
      **54 tests pass**.

### P2 — cleanups

- [ ] Suppress the STC warning when the PDF contains no STC rows (`:326`).
- [ ] Report the dropped-line count per category, and stop truncating the sample to 80 chars
      (`:308`); the truncation is what made the original warning misleading.

### Not verified — do not assume

- [ ] STC column semantics (`:283`–`:297`), including the trailing `pen` value that is recorded
      but deliberately not promoted to `synchronization_total`.
- [ ] Aggregate and "Final"/"Final" summary PDFs — they contain 0 scoring rows and were skipped.

---

## Verification

Reproduce the drop list (needs the regexes inlined; they are local to the function body):

```powershell
python C:\Users\linma\AppData\Local\Temp\opencode\dump41.py
```

Expected: `DROPPED SCORING LINES: 41`, split 23 / 18 / 9.

Full test suite:

```powershell
python -m unittest discover -s tests -t .
```

Log integrity after any edit:

```powershell
$t = Get-Content -LiteralPath "Logs to build dashboard.md" -Raw
([regex]::Matches($t,'(?m)^```')).Count          # 62, must be even
([regex]::Matches($t,'<details>')).Count          # 26
([regex]::Matches($t,'(?m)^<summary><h2>')).Count # 26, all unique
([regex]::Matches($t,'ssk_live_[A-Za-z0-9]{6}\.[A-Za-z0-9]{20}')).Count  # must be 0
```

---

## Key file references

| Location | What |
|---|---|
| `scripts/ingest_routines.py:237` | `el_match` — 4 judges, hardcoded trailing pair |
| `scripts/ingest_routines.py:249` | `element_total` assigned, never summed |
| `scripts/ingest_routines.py:266` | `ai_match` — 4 judges, single optional trailing |
| `scripts/ingest_routines.py:283` | `sy_match` — STC path, unverified |
| `scripts/ingest_routines.py:308` | dropped-line collection, truncated to 80 chars |
| `scripts/ingest_routines.py:320` | warning — reports only the first line |
| `scripts/ingest_routines.py:326` | STC warning — emitted unconditionally |
| `scripts/ingest_routines.py:71` | `extract_text_from_pdf` — pdfplumber `extract_text()` |
| `scripts/user_mgmt_sync.py` | `synchronized_meet` — prints API keys to stdout |
| `swim-meets/2026/20260305_WestZone_Sacramento_CA/AG 12U Female Solo Details.pdf` | source PDF |