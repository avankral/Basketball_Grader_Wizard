# Basketball Grader Wizard — Implementation Plan

## TL;DR

Build a Streamlit dashboard that ingests "Club Grading Book" Excel files, analyzes team performance using **Strength of Schedule (SoS)** methodology, and generates transparent, defensible grade movement recommendations. The system identifies grading anomalies (teams playing outside their assigned grade, transitive variance issues) and produces exportable justifications suitable for appeals to league administration (DVBA).

---

## Domain Knowledge (from DVBA Expert)

### Grading Group Structure

| Group       | Grades        | Description                                           |
| ----------- | ------------- | ----------------------------------------------------- |
| **Group 1** | A, B1, B2, B3 | Top tier — elite basketball, big step between A and B |
| **Group 2** | B, C1, C2     | Good quality teams with decent players                |
| **Group 3** | C, D          | Emerging teams, developing skillset                   |

> B1, B2, B3 exist to avoid grades below D (negative connotation)

### Color Coding in Source Data

| Color        | Meaning                          | Interpretation          |
| ------------ | -------------------------------- | ----------------------- |
| 🟢 Green     | Win with high variance           | Dominant win            |
| 🔵 Blue      | Win with extremely high variance | Blowout win             |
| 🔴 Dark red  | Loss with moderate-high variance | Bad loss                |
| 🟠 Light red | Moderate-high loss               | Concerning loss         |
| ⬜ White     | Competitive game                 | Correct grade placement |

### Critical Columns in Source Excel

| Column  | Content                                   |
| ------- | ----------------------------------------- |
| B       | Team name (e.g., "Jets U12 Girls 2")      |
| C       | **Recommended grade** from DVBA           |
| I, O, U | Round 1, 2, 3 results (with color coding) |

### Key Grading Issues to Detect

1. **Transitive Variance Problem**

   > Example: Bulls def Watsonia 78-38, then Watsonia def Jets 50-18 → implies 70+ point variance against Jets

2. **Grade Mismatch During Grading**

   > Example: Jets U18 Boys 1 placed in D grade but never played any D-grade teams during grading rounds (played mostly C1) — will annihilate D teams

3. **Strength of Schedule Weighting**
   > Losing competitively to A-grade team counts MORE than winning by 15 against B-grade
   > Must track opponent's grade at time of play, not just result

---

## Source Data Structure (Confirmed)

**File:** `Autumn 2026 Club Grading Book Rd5.xlsx`

**Sheet naming:** `{Gender}{Age}{Division}` — e.g., `B161`, `G122`

- First char: `B` (Boys) or `G` (Girls)
- Next 2 chars: Age group (e.g., `16` = U16)
- Last char: Division/Grading Group number (1, 2, etc.)

**Columns (wide format, repeating per round):**
| Column | Example | Notes |
|--------|---------|-------|
| Row # | 1 | Index |
| Team | Apollo U16 Boys 1 | Full team name |
| Grade | A, B1, B2, C | **Recommended grade** (DVBA assignment) |
| Rank | 2 | Current standings rank |
| Result | Won / Lost / DNP | DNP = Did Not Play |
| Score | "31 - 56" | String to parse |
| Margin | -25 | **Pre-calculated** — negative = loss |
| Opponent | Yarrambat U16 Boys 1 | Opponent team name |
| Sheet Code | B161 | Cross-reference to sheet |
| Description | "Lost against..." | Human-readable summary |

_Columns repeat for each round (Rnd 1, Rnd 2, ... Rnd N)_

---

## Phase 1: Data Pipeline & Domain Model

_Foundation for all features — must complete first_

1. **Define data schema** in `src/models/`
   - `game_result.py` — Pydantic models:
     - `GameResult`: team, opponent, opponent_grade, score_for, score_against, margin, result (W/L/DNP), round_num
     - `TeamSeason`: team_name, gender, age_group, division, assigned_grade, games: List[GameResult]
   - Parse gender/age/division from sheet name regex: `^([BG])(\d{2})(\d+)$`
   - Validation: margin = score_for - score_against, grade format regex

2. **Build wide-to-long parser** in `src/data/parser.py`
   - Read all sheets from Excel file
   - Detect round columns dynamically (find "Rnd N" headers)
   - **Extract opponent grade** by cross-referencing opponent name to their assigned grade
   - Unpivot/melt wide format → one row per game
   - Parse score strings: `"31 - 56"` → `(31, 56)`
   - **Detect cell colors** (openpyxl fill colors) for variance classification
   - Skip `DNP` rows
   - Return `List[TeamSeason]` with embedded games

3. **Implement Parquet storage layer** in `src/data/storage.py`
   - Storage: `data/{season}/games.parquet` (long format)
   - Columns: team, opponent, opponent_grade, score_for, score_against, margin, result, round, gender, age_group, division, assigned_grade, variance_class
   - Append new rounds, deduplicate by (team, opponent, round)
   - Query functions: `get_team_history()`, `get_round_results()`, `get_rolling_window()`

4. **Add dependencies** to `pyproject.toml`
   - `openpyxl>=3.1.0` (Excel parsing + cell colors)
   - `pydantic>=2.0`

5. **Unit tests** in `tests/test_data_pipeline.py`
   - Test sheet name parsing
   - Test wide-to-long transformation
   - Test score string parsing
   - Test opponent grade extraction
   - Test color detection
   - Test DNP handling
   - Test Parquet round-trip

**Verification:**

- [ ] `Autumn 2026 Club Grading Book Rd5.xlsx` parses all sheets
- [ ] Long-format DataFrame has expected columns including `opponent_grade`
- [ ] Cell colors correctly mapped to variance classification
- [ ] Parquet files persist correctly
- [ ] `pytest tests/test_data_pipeline.py -v` passes

---

## Phase 2: Strength of Schedule & Analytics Engine

_Core innovation — weighted analysis based on opponent quality_

6. **Define grade hierarchy** in `src/grading/grades.py`
   - Ordered grade list: `["A", "B1", "B2", "B3", "C1", "C2", "D"]`
   - Grade distance function: `grade_distance("A", "C1") → 3`
   - Functions: `grade_above()`, `grade_below()`, `can_promote()`, `can_demote()`

7. **Build Strength of Schedule (SoS) engine** in `src/grading/strength_of_schedule.py`
   - `calculate_sos(team, games)` → `StrengthOfSchedule` dataclass:
     - `opponent_grades_faced`: Counter of grades played against
     - `avg_opponent_grade_rank`: Numeric average (A=1, B1=2, etc.)
     - `grade_coverage`: Did team play in their assigned grade?
     - `played_above_count`, `played_below_count`, `played_at_grade_count`
   - **Key insight**: Flag teams who never played opponents in their assigned grade

8. **Build fairness metrics engine** in `src/grading/metrics.py`
   - `calculate_team_stats(team, games)` → `TeamMetrics` dataclass:
     - `wins`, `losses`, `dnp_count`
     - `avg_margin`, `total_margin`
     - `blowout_wins` (margin > threshold)
     - `blowout_losses` (margin < -threshold)
     - `close_games` (abs(margin) ≤ threshold)
     - **Weighted metrics** (adjusted by opponent grade):
       - `weighted_wins`: Win vs A-grade = 1.5, vs same grade = 1.0, vs lower = 0.7
       - `weighted_losses`: Loss vs A-grade = 0.7, vs same grade = 1.0, vs lower = 1.5
   - Configurable thresholds in `config/settings.py`:
     - `BLOWOUT_MARGIN = 20` points
     - `CLOSE_GAME_MARGIN = 5` points
     - `MIN_GAMES_FOR_RECOMMENDATION = 3`
     - `ROLLING_WINDOW_ROUNDS = 5`
     - `GRADE_WEIGHT_UP = 1.5` (playing up bonus)
     - `GRADE_WEIGHT_DOWN = 0.7` (playing down penalty)

9. **Build transitive analysis engine** in `src/grading/transitive.py`
   - Detect transitive variance chains:
     - If A beat B by 40, and B beat C by 30, flag potential 70-point variance
   - `find_transitive_chains(team, depth=2)` → List of variance paths
   - Output: "Bulls def Watsonia 78-38, Watsonia def Jets 50-18 → 70+ point implied variance"

10. **Create recommendation engine** in `src/grading/recommender.py`
    - `RecommendationType` enum: `PROMOTE`, `DEMOTE`, `MONITOR`, `NO_CHANGE`, `REVIEW_NEEDED`
    - `Recommendation` dataclass with:
      - `recommendation_type`
      - `confidence`: HIGH / MEDIUM / LOW
      - `explanation`: Human-readable justification
      - `evidence`: List of supporting game results
      - `concerns`: List of ambiguous factors
    - **Transparent rules** (for parent/admin communication):
      - **PROMOTE**: 3+ blowout wins, no blowout losses, SoS indicates playing down
      - **DEMOTE**: 3+ blowout losses, no blowout wins, SoS indicates playing up
      - **REVIEW_NEEDED**: Never played at assigned grade, or transitive variance detected
      - **MONITOR**: 2 blowout games (approaching threshold)
      - **NO_CHANGE**: Balanced results at correct SoS level
    - Example explanation:
      > _"Jets U18 Boys 1 (Assigned: D): REVIEW_NEEDED — Team played 0 games against D-grade opponents (played 3 games vs C1). Based on competitive results against C1 teams, D-grade placement will likely result in mismatches."_

11. **Admin override system** in `src/grading/overrides.py`
    - `Override` model: team, original_rec, admin_decision, reason, timestamp
    - Persist to `data/overrides.parquet`
    - Audit log: query by team, date, or admin action

12. **Unit tests** in `tests/test_grading.py`
    - Test SoS calculation with known opponent grades
    - Test weighted metrics
    - Test transitive chain detection
    - Test recommendation logic with edge cases
    - Test override persistence

**Verification:**

- [ ] SoS correctly identifies teams playing outside their grade
- [ ] Weighted metrics reward playing up, penalize playing down
- [ ] Transitive chains detected for sample data
- [ ] Correct recommendations for sample teams from Rd5 data
- [ ] Explanations are human-readable and defensible
- [ ] `pytest tests/test_grading.py -v` passes

---

## Phase 3: Dashboard UI

_Depends on Phases 1-2_

13. **Sidebar filters** in `src/ui/filters.py`
    - **Season selector**: Autumn/Summer + Year
    - **Round selector**: Slider 1–N (auto-detect from data)
    - **Gender**: Boys / Girls / Both
    - **Age group**: Multi-select (U8–U18, derived from sheet names)
    - **Division/Grading Group**: Multi-select (1, 2, 3, etc.)
    - **Grade filter**: Optional A/B1/B2/etc.
    - **Club filter**: Focus on specific club (e.g., "Jets")
    - All filters update `st.session_state`

14. **Data upload view** — enhance `src/app.py` Upload tab
    - File uploader for `.xlsx` (Club Grading Book format)
    - Preview: show detected sheets, row counts, color summary
    - Validation feedback: parsing errors, warnings
    - "Process & Save" button → Parquet storage

15. **Standings table view** — Data tab
    - Group by: Gender → Age Group → Grading Group → Grade
    - Columns: Rank, Team, Assigned Grade, W, L, PF, PA, +/-, Blowout W, Blowout L, **SoS Score**, **Grade Coverage**
    - Row highlighting: 🟢 promote, 🟡 monitor, 🔴 demote, ⚠️ review needed
    - Sortable columns, download as Excel

16. **Strength of Schedule view** — new tab
    - Per-team breakdown: Opponents faced, their grades, results
    - Visual: Heatmap of grade levels played vs assigned grade
    - Flag: "Never played at assigned grade" warnings
    - Transitive variance chains displayed

17. **KPI cards** in `src/ui/metrics_cards.py`
    - Total teams across all sheets
    - Games played this round
    - Recommendations pending (Promote + Demote + Review count)
    - **Grade mismatches detected** (teams not playing at assigned level)
    - Overrides applied this season
    - Shared blue styling from `src/styles.py`

18. **Trend charts** using Plotly in `src/ui/charts.py`
    - **Margin trend**: Line chart per team over rounds
    - **SoS distribution**: Box plot per grade
    - **Grade coverage**: Stacked bar showing % games at/above/below grade
    - **Blowout frequency**: Bar chart per division

19. **Recommendations panel** — new tab
    - Table: Team, Assigned Grade, Recommendation, Confidence, Explanation, Actions
    - Filter: Pending Only / Review Needed / All
    - Expandable row: Full evidence + concerns
    - "Accept" button → applies recommendation
    - "Override" button → modal with reason input
    - Bulk actions: "Accept All High-Confidence" / "Export Pending"

20. **Team Deep Dive** — new tab
    - Select team from dropdown
    - Full game history with opponent grades
    - SoS breakdown
    - Transitive variance chains involving this team
    - **Generate Appeal** button → exports justification document

21. **Audit log viewer** — admin view
    - Table: Date, Team, Original Rec, Admin Decision, Reason
    - Filter by team, date range, action type
    - Export to Excel

**Verification:**

- [ ] Filters reactively update all views
- [ ] SoS view correctly shows opponent grade distribution
- [ ] Grade mismatch warnings appear for affected teams
- [ ] Transitive chains display correctly
- [ ] Recommendations show with confidence levels
- [ ] Manual walkthrough of full workflow

---

## Phase 4: Export & Reports

_Parallel with Phase 3 — critical for DVBA communication_

22. **Excel export** in `src/exports/excel.py`
    - Full standings export per age group
    - Recommendations report with explanations
    - **SoS analysis export** per team
    - Use `openpyxl` for themed formatting

23. **Appeal document generator** in `src/exports/appeal.py`
    - Per-team justification document
    - Format suitable for submission to DVBA
    - Includes:
      - Team info and assigned grade
      - SoS analysis (opponents faced, grades played)
      - Result summary with context
      - Transitive variance concerns
      - Recommendation with full evidence
    - Export as Word/PDF

24. **PDF reports** in `src/exports/pdf.py`
    - Weekly summary: recommendations + standings snapshot
    - Club-specific report (e.g., all Jets teams)
    - Use `reportlab` or `weasyprint`
    - Branded header, logo from `assets/`

25. **Download buttons** in UI
    - "Export Standings (Excel)" button
    - "Download Recommendations (PDF)" button
    - "Generate Appeal for [Team]" button
    - "Export Club Report (Jets)" button
    - "Export Audit Log (Excel)" button

**Verification:**

- [ ] Excel files open correctly in Excel
- [ ] Appeal documents contain all required justification
- [ ] PDF renders with proper formatting
- [ ] All exports include correct data scope (filtered by selections)

---

## Phase 5: Future Round Optimization (Stretch Goal)

_Utopia feature — propose optimal matchups for data gathering_

> **Critical insight from DVBA:** Teams change significantly between seasons, so there is no historical continuity. This makes early-round scheduling (Rd 1-2) critical — these games establish baseline data. Avoid "empty calorie" games that provide no information (blowout mismatches).

26. **Matchup optimizer** in `src/scheduling/optimizer.py`
    - After each round, propose matchups that maximize information gain
    - Priority: Teams with low grade coverage should play at their assigned grade
    - **Avoid "empty calorie" games**: Flag proposed matchups between teams with high predicted variance
    - Detect cross-division drops: If team is losing badly in B161, suggest B162 matchups
    - Output: Suggested schedule for next round with confidence scores

27. **What-If Analysis** in UI
    - "If Team A plays Team B, what would we learn?"
    - Projected grade confidence after hypothetical result
    - "Empty calorie" warning for mismatched proposals

28. **Early-Round Audit**
    - Flag Round 1-2 schedules that contain likely mismatches
    - Report: "These teams played no informative games in grading rounds"

**Note:** This is a stretch goal for v2. Focus on Phases 1-4 first.

---

## Phase 6: Polish & Deployment Readiness

_Final phase_

28. **Error handling & validation**
    - User-friendly error messages for bad XLS uploads
    - Edge case handling: empty data, partial weeks, missing colors

29. **Performance optimisation**
    - Apply `@st.cache_data` to data loading (TTL = 300s)
    - Lazy loading for large datasets

30. **Documentation**
    - Update `README.md` with user guide
    - Add `docs/ADMIN_GUIDE.md` explaining grading logic
    - Add `docs/APPEAL_TEMPLATE.md` for DVBA submissions
    - Add `docs/DATA_FORMAT.md` with XLS requirements

31. **Integration tests** in `tests/test_integration.py`
    - End-to-end: upload → analyze → recommend → appeal → export

**Verification:**

- [ ] Full workflow test with sample data
- [ ] Lint passes: `ruff check .`
- [ ] All tests pass: `pytest -v`

---

## Relevant Files

**Existing (to modify):**

- `src/app.py` — Main entry, add tabs for upload/recommendations/SoS/deep-dive
- `config/settings.py` — Add grading thresholds, SoS weights, rolling window config
- `src/styles.py` — Already complete, reuse shared theme components
- `pyproject.toml` — Add `openpyxl`, `pydantic`, `reportlab`, `python-docx` dependencies

**New files to create:**

```
src/
├── models/
│   ├── __init__.py
│   ├── game_result.py      # Pydantic: GameResult, TeamSeason
│   └── recommendation.py   # Pydantic: Recommendation, Override
├── data/
│   ├── __init__.py
│   ├── parser.py           # Wide-to-long Excel parser + color detection
│   └── storage.py          # Parquet persistence layer
├── grading/
│   ├── __init__.py
│   ├── grades.py           # Grade hierarchy logic
│   ├── strength_of_schedule.py  # SoS calculations
│   ├── metrics.py          # TeamMetrics + weighted calculations
│   ├── transitive.py       # Transitive variance chain detection
│   ├── recommender.py      # Recommendation engine
│   └── overrides.py        # Admin override + audit
├── ui/
│   ├── __init__.py
│   ├── filters.py          # Sidebar filter components
│   ├── metrics_cards.py    # KPI card components
│   ├── charts.py           # Plotly visualizations
│   ├── sos_view.py         # Strength of Schedule tab
│   └── team_deep_dive.py   # Team analysis tab
├── exports/
│   ├── __init__.py
│   ├── excel.py            # Excel export
│   ├── pdf.py              # PDF report generation
│   └── appeal.py           # Appeal document generator
└── scheduling/
    ├── __init__.py
    └── optimizer.py        # Future round matchup optimizer (stretch)

tests/
├── conftest.py             # Fixtures, sample data
├── test_data_pipeline.py   # Parser + storage tests
├── test_grading.py         # Metrics + SoS + recommender tests
├── test_transitive.py      # Transitive chain tests
└── test_integration.py     # End-to-end workflow tests

docs/
├── ADMIN_GUIDE.md          # Grading logic explanation (for parents)
├── APPEAL_TEMPLATE.md      # Template for DVBA submissions
└── DATA_FORMAT.md          # Excel file requirements
```

**Sample data for testing:**

- `data/Autumn 2026 Club Grading Book Rd5.xlsx` — Real data, 5 rounds

---

## Decisions Made

| Decision                           | Rationale                                                                                     |
| ---------------------------------- | --------------------------------------------------------------------------------------------- |
| **Blowout margin = 20 points**     | Confirmed — same for all age groups                                                           |
| **Same thresholds all ages**       | Simpler to explain to parents                                                                 |
| **Strength of Schedule weighting** | Playing up should count more than playing down                                                |
| **Grade weight: up=1.5, down=0.7** | Reward competitive losses against better teams                                                |
| **Transitive variance detection**  | Catches hidden mismatches (A beats B, B beats C)                                              |
| **REVIEW_NEEDED category**         | Flags ambiguous cases requiring human judgment                                                |
| **Appeal document export**         | Enables formal DVBA submissions with evidence                                                 |
| Pydantic for data models           | Type safety + validation + clear error messages                                               |
| Parquet storage                    | Efficient storage + fast historical queries                                                   |
| Override audit log                 | Accountability and transparency                                                               |
| **No cross-season continuity**     | Teams change too much between seasons (rosters, development). Treat each season independently |
| **Cross-division games allowed**   | Teams can drop from B161 to B162 if losing badly. Parser handles cross-sheet opponents        |
| **Dynamic grade extraction**       | Parse grades from data rather than hardcoding — allows for future grade structure changes     |

---

## Scope Boundaries

**In scope:**

- Club Grading Book Excel upload and parsing (wide-format, multi-sheet)
- Cell color detection for variance classification
- Strength of Schedule analysis with grade-weighted metrics
- Transitive variance chain detection
- Grade movement recommendations with confidence levels
- Exportable appeal documents for DVBA
- Admin dashboard with filters, standings, SoS view, Plotly charts
- Override capability with audit log
- PDF and Excel exports
- Club-specific filtering (e.g., Jets focus)
- Rolling window analysis (5 rounds default)

**Out of scope (v1):**

- Multi-user authentication (admin-only for now)
- Real-time notifications
- Automated grade application (recommend only, never force)
- Mobile-responsive design (desktop-first)
- API endpoints (Streamlit-only)
- Future round matchup optimization (stretch goal for v2)

---

## Open Items

### Resolved ✅

1. **Cross-division games**: ✅ **Yes, teams can play across divisions.** If a team is at the bottom of B161 and losing games, they can drop into B162. The parser must handle cross-sheet opponent references.

2. **Grade values**: ✅ **Extract from data.** Parse unique grades from the "Grade" column across all sheets to build the complete list dynamically.

3. **Multiple seasons**: ✅ **No continuity between seasons.** Teams change significantly each season (roster changes, player development, etc.). Each season is treated independently. This is why early-round scheduling is critical — Round 1 and 2 matchups must maximize information gain to avoid **"empty calorie" games** (meaningless matchups between over/undermatched teams that teach us nothing about true team strength).

### Remaining (Verify in Phase 1)

4. **Color hex codes**: Extract exact Excel color codes for variance classification
5. **Club name extraction**: Regex pattern to extract club from team name (e.g., "Jets" from "Jets U12 Girls 2")

---

## Domain Insight: "Empty Calorie" Games

> _"You want to avoid the 'empty calorie' games where you learn nothing about the teams by playing a meaningless game by playing over/undermatched teams against each other."_ — domain expert

This insight directly informs Phase 5 (Future Round Optimization). The matchup optimizer should:

- Prioritize games between teams with uncertain grade placement
- Avoid repeating blowout matchups (already know the outcome)
- Ensure teams play at or near their assigned grade level early in grading rounds
- Flag when a proposed schedule contains "empty calorie" games
