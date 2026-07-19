# Prompts to load data from Figure result

## 2026-07-17

enhance the script `ingest_figures.py` to use the event existing in the table. The existing criteria is the event_name existing in the `as_event` table, then use the existing event id to load the other data from the PDF file.

enhance the script `ingest_figures.py` to correctly parse a swimmer's result crossing the pages. Currently swimmer WEARN Coralie lost the figure scores in the page 7

The script `ingest_figures.py` works for the other Figure meet result PDF files. But when loading `swim-meets/2026/CharlotteDavisRegionAChampionship/Intermediate 10U Figures - Detailed .pdf` to tables, there are a few issues

1. missed data loading to `as_event`. In this PDF file, the event should be `2026 Charlotte Davis Region A Championship`, see the sample data from the PDF below.
2. missed data loading to `as_meet`. In this PDF file, the meet should be `Intermediate 10 and Under Figures`, see the sample data from the PDF below.
3. missed data loading to `as_figure`. In this PDF file, see the sample data as from the PDF below.
   (meet_id, figure_code="Figure 2", figure_code_short = "F2", name = "Barracuda", degree_difficulty=1.8, created_at)
4. missing data loading to `as_figure_judge_panel`. In this PDF file, see the sample data as from the PDF below.
5. in the as_figure_judge_panel
   add a new row to import the referee infomation
   (meet_id, figure_id = null, figure_code_short = null, figure_name = Referee, panel = {"Referee": "Leslie SIMS"}, created_at)

```text
2026 Charlotte Davis Region A Championship
Intermediate 10 and Under Figures
                                        17 MAY 2026
                                   Referee: Leslie SIMS
     F2: Barracuda           F3: Tower               F4: Walkover Back
     DD: 1.8                 DD: 1.9                 DD: 1.9
J1   Elaine HENRICKSEN       Isabelle PETRICEK
J2   Christine ZGOMBIC       Kristen SCHMEDEMANN
J3   Lucie SVRCINOVA         Jocilyn SAYLER
J4   Hui ZHEN                Elizabeth GROSSBERG
J5   Taylor MIRON            Jordan LEE
```

```text
Figure 2     Barracuda                         1.8
Figure 3     Tower                             1.9
Figure 4     Walkover Back                     1.9
                                     Total:    5.6
```

## 2026-07-16

When loading `swim-meets/2026/JuniorOlympicChampionships/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf` to table `as_meet_figure_result`:

1. missing `athlete_name`

**AI Fixed this issue** --

In Event **Junior Olympic Championships**, in [PDF 1] result, **Age Group 12 and Under Figures**, `F4` judge panel, there is `J5` **Heidi LURENZ**. Please modify the script to check if `J5` exists, load `J5` to the `as_figure_judge_panel` table, and also modify the python scripts to load `J5` result to `as_meet_figure_result`.

---

## 2026-07-15

Update the scripts to load Judge Panel information to table `as_figure_judge_panel` with the information of figure judge panels.

- `id`: UUID
- `meet_id`: UUID, referenced to `as_meet`
- `figure_id`: UUID, referenced to `as_figure`
- `figure_code_short`: string, eg. `F1`
- `figure_name`: string, eg. `Straight Ballet Leg`
- `panel`: json, eg, `{"J1": "Karen ROSOLOWSKI", "J2": "Svetlana MALINOVSKAYA", "J3": "Shannon KORPELA", "J4": "Caroline KAROLINKO"}`

The data is from the upper parts of the figure result PDF page 1. Sample data in the PDF is below. When importing the data, please don't create duplicated data rows. And reference the table `as_figure` for figure information, eg. for `F1`, we can use `Figure 1` in the `as_figure` table.

```text
F1: Straight Ballet Leg F2: Barracuda F3: Kip F4: Swanita Spinning 18
DD: 1.6 DD: 1.8 DD: 1.6 DD: 1.9
J1 Karen ROSOLOWSKI Darcee REDDING Ginny JASONTEK Krista KARWOSKY
J2 Svetlana MALINOVSKAYA Cheryl RUSSELL Debbie LATCHFORD Victoria ANDERSON
J3 Shannon KORPELA Sandra MAHONEY Linda WITTER Eugenia GILLIAN
J4 Caroline KAROLINKO Heidi LURENZ Sheila MCNABB Olivia ZHANG
```

---

## 2026-07-15

The code generated to import the result is almost great, the only tuning needed is to enhance the Judge Panel part.
I am making a copy in folder `2026summerproject00-onlyJudgePanelNeed2Enhance`.

### Prompts to load Artistic Swimming Competition results (PDF) to database

Modify the previous SQL script `sql/create_figures_table.sql`, and python scripts in the `scripts` folder. Think deeply to follow the instructions:

Scan figure scores PDF file [Detailed\_-_Age_Group_12_and_Under_Figures.pdf](file:///C:/Users/linma/workspace/02-learning-AI/2026summerproject/swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf) to modify the existing Python scripts to make the data export process more accurate.

Follow the data modeling below:

0. Connect with local Docker Desktop hosted Supabase DB `AS_Event_DB` to load the Artistic Swim meet result.

Here are a few enhancements to parse the figure result from the PDF:

1. Create a table `as_event` to store the Artistic Swimming Event information:
   - `id`: UUID
   - `event_name`: string, eg. `2026 Youth Championship and 12u Invitational` in the PDF
   - `host_city`: string, eg. `Buffalo, NY`
   - `event_date`: date: eg. `04/23/2026`, converted from `"23 APR 2026"`
     _(The data is from the Header part of the PDF.)_

2. Create a table `as_meet` to store the meet information:
   - `id`: UUID
   - `name`: string, eg. `Age Group 12 and Under Figures`
   - `meet_date`: date, eg. `04/23/2026`
     _(The data is from the Header part of the PDF.)_

3. Create a table `as_figure` to store the figures information for the meet:
   - `id`: UUID
   - `meet_id`: UUID, referenced to the `as_meet`
   - `figure_code`: string, eg. `Figure 1`
   - `figure_code_short`: string, eg. `F1`
   - `name`: string, eg. `Straight Ballet Leg`
   - `degree_difficulty`: decimal, eg. `1.6`

   _(The data is from the upper parts of the figure result PDF page 1. Sample data in the PDF:)_

   ```text
   Figure 1 Straight Ballet Leg 1.6
   Figure 2 Barracuda 1.8
   Figure 3 Kip 1.6
   Figure 4 Swanita Spinning 180° 1.9
   Total: 6.9
   ```

4. Change `figure_judges` table to `as_figure_judge_panel` with the information of figure judge panels:
   - `id`: UUID
   - `meet_id`: UUID, referenced to `as_meet`
   - `figure_id`: UUID, referenced to `as_figure`
   - `panel`: json
   - `judge_code`: string, eg. `J1`
   - `judge_name`: string, eg. `Karen ROSOLOWSKI`

   _(The data is from the upper parts of the figure result PDF page 1. Sample data in the PDF as below. When importing the data, please don't create duplicated data row. And referenced to the table `as_figure` for figure information, eg. `F1`, we can use `Figure 1` in the `as_figure` table.)_

   ```text
    F1: Straight Ballet Leg F2: Barracuda           F3: Kip                 F4: Swanita Spinning 18
        DD: 1.6                 DD: 1.8                 DD: 1.6                 DD: 1.9
   J1   Karen ROSOLOWSKI        Darcee REDDING          Ginny JASONTEK          Krista KARWOSKY
   J2   Svetlana MALINOVSKAYA   Cheryl RUSSELL          Debbie LATCHFORD        Victoria ANDERSON
   J3   Shannon KORPELA         Sandra MAHONEY          Linda WITTER            Eugenia GILLIAN
   J4   Caroline KAROLINKO      Heidi LURENZ            Sheila MCNABB           Olivia ZHANG
   ```

5. Create table `as_meet_figure_result` to load the figure meet result.

Here are 2 rows of result from the PDF for swimmer SHEN Jasper and CHU Peishan:

```text
Code Rank Draw Swimmer J1 J2 J3 J4 Pen. Total Routine
1.   (136) UNF - UNAFFILIATED CLUB
                SHEN Jasper [2014]
                      Fig #1     6.8  6.6  6.1  6.6          6.5750  70.4360
                      Fig #2     7.5  8.3  8.0  7.9          7.9417
                      Fig #3     6.4  6.7  6.4  6.4          6.4250
                      Fig #4     7.0  7.3  7.2  7.0          7.1083

 2.   (118) GSA - GOLDEN STATE AQUABELLES
                CHU Peishan [2014]
                      Fig #1     6.3  7.0  6.3  6.8          6.5667  69.2560
                      Fig #2     7.3  7.6  6.7  7.4          7.3167
                      Fig #3     6.6  7.0  6.2  6.5          6.5583
                      Fig #4     7.0  7.7  6.8  7.3          7.1667
```

Schema:

- `id` uuid NOT NULL DEFAULT `gen_random_uuid()`
- `meet_id` uuid, referenced to `as_meet`
- `rank` text COLLATE pg_catalog."default", eg. `1` from the first row in the PDF file
- `draw` text COLLATE pg_catalog."default"
- `team_code` text COLLATE pg_catalog."default"
- `team_name` text COLLATE pg_catalog."default"
- `athlete_name` text COLLATE pg_catalog."default"
- `athlete_birth_year` integer
- `penalty` text COLLATE pg_catalog."default"
- `total_score` numeric, eg. `28.05` (= 6.5750 + 7.9417 + 6.4250 + 7.1083)
- `routine_score` numeric, eg. `70.436`
- `figure_scores` jsonb, eg. as below:

```json
[
  {
    "judge_scores": [6.8, 6.6, 6.1, 6.6],
    "figure_number": 1,
    "total_score": 6.575,
    "routine_score": 70.436
  },
  {
    "judge_scores": [7.5, 8.3, 8.0, 7.9],
    "figure_number": 2,
    "total_score": 7.9417,
    "routine_score": 0
  },
  {
    "judge_scores": [6.4, 6.7, 6.4, 6.4],
    "figure_number": 3,
    "total_score": 6.425,
    "routine_score": 0
  },
  {
    "judge_scores": [7.0, 7.3, 7.2, 7.0],
    "figure_number": 4,
    "total_score": 7.1083,
    "routine_score": 0
  }
]
```

- `source_file` text COLLATE pg*catalog."default", eg. `swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed*-\_Age_Group_12_and_Under_Figures.pdf`
- `created_at` timestamp with time zone DEFAULT `now()`

---

## Prompts to load Artistic Swimming Competition results (PDF) to database

Scan figure scores PDF file [Detailed\_-_Age_Group_12_and_Under_Figures.pdf](file:///C:/Users/linma/workspace/02-learning-AI/2026summerproject/swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf)

0. Connect with local Docker Desktop hosted Supabase DB `AS_Event_DB` to load the Artistic Swim meet result.

Here are a few enhancements to parse the figure result from the PDF:

1. Create a table `as_event` to store the Artistic Swimming Event information:
   - `id`: UUID
   - `event_name`: string, eg. `2026 Youth Championship and 12u Invitational` in the PDF
   - `host_city`: string, eg. `Buffalo, NY`
   - `event_date`: date: eg. `04/23/2026`, converted from `"23 APR 2026"`
     _(The data is from Header part of the PDF.)_

2. Create a table `as_meet` to store the meet information:
   - `id`: UUID
   - `name`: string, eg. `Age Group 12 and Under Figures`
   - `meet_date`: date, eg. `04/23/2026`
     _(The data is from Header part of the PDF.)_

3. Create a table `as_figure` to store the figures information for the meet:
   - `id`: UUID
   - `meet_id`: UUID, referenced to the `as_meet`
   - `figure_code`: string, eg. `Figure 1`
   - `figure_code_short`: string, eg. `F1`
   - `name`: string, eg. `Straight Ballet Leg`
   - `degree_difficulty`: decimal, eg. `1.6`

   _(The data is from the upper parts of the figure result page 1. Sample data in the PDF:)_

   ```text
   Figure 1 Straight Ballet Leg 1.6
   Figure 2 Barracuda 1.8
   Figure 3 Kip 1.6
   Figure 4 Swanita Spinning 180° 1.9
   Total: 6.9
   ```

4. Change `figure_judges` table to `as_figure_judge_panel` with the info:
   - `id`: UUID
   - `meet_id`: UUID, referenced to `as_meet`
   - `figure_id`: UUID, referenced to `as_figure`
   - `panel`: json
   - `judge_code`: string, eg. `J1`
   - `judge_name`: string, eg. `Karen ROSOLOWSKI`

5. Create table `as_meet_figure_result` to load the figure meet result.

Here are 2 rows of result from the PDF for swimmer SHEN Jasper and CHU Peishan:

```text
Code Rank Draw Swimmer J1 J2 J3 J4 Pen. Total Routine 1. (136) UNF - UNAFFILIATED CLUB
SHEN Jasper [2014]
Fig #1 6.8 6.6 6.1 6.6 6.5750 70.4360
Fig #2 7.5 8.3 8.0 7.9 7.9417
Fig #3 6.4 6.7 6.4 6.4 6.4250
Fig #4 7.0 7.3 7.2 7.0 7.1083
```

Schema:

- `id` uuid NOT NULL DEFAULT `gen_random_uuid()`
- `meet_id` uuid, referenced to `as_meet`
- `rank` text COLLATE pg_catalog."default", eg. `1` from the first row in the PDF file
- `draw` text COLLATE pg_catalog."default"
- `team_code` text COLLATE pg_catalog."default"
- `team_name` text COLLATE pg_catalog."default"
- `athlete_name` text COLLATE pg_catalog."default"
- `athlete_birth_year` integer
- `penalty` text COLLATE pg_catalog."default"
- `total_score` numeric, eg. `28.05` (= 6.5750 + 7.9417 + 6.4250 + 7.1083)
- `routine_score` numeric, eg. `70.436`
- `figure_scores` jsonb, eg. as below:

```json
[
  {
    "judge_scores": [6.8, 6.6, 6.1, 6.6],
    "figure_number": 1,
    "routine_score": 6.575
  },
  {
    "judge_scores": [7.5, 8.3, 8.0, 7.9],
    "figure_number": 2,
    "routine_score": 7.9417
  },
  {
    "judge_scores": [6.4, 6.7, 6.4, 6.4],
    "figure_number": 3,
    "routine_score": 6.425
  },
  {
    "judge_scores": [7.0, 7.3, 7.2, 7.0],
    "figure_number": 4,
    "routine_score": 7.1083
  }
]
```

- `source_file` text COLLATE pg*catalog."default", eg. `C:\Users\linma\workspace\02-learning-AI\2026summerproject\swim-meets\2026\YouthChampionshipand12uinvitational\figure\Detailed*-\_Age_Group_12_and_Under_Figures.pdf`
- `created_at` timestamp with time zone DEFAULT `now()`

---

## Prompts to fix the error

Scan the PDF to fix the issue -

```text
(.venv) PS C:\Users\linma\workspace\02-learning-AI\2026summerproject> python scripts/ingest_figures.py "swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf"
Processing: swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf
Parsed meet metadata plus 4 judges, 4 routines, and 136 athletes.
Failed to insert to Supabase: Expecting value: line 1 column 1 (char 0)
```

---

## Prompts to load the PDFs

Scan figure scores PDF file again [Detailed\_-_Age_Group_12_and_Under_Figures.pdf](file:///C:/Users/linma/workspace/02-learning-AI/2026summerproject/swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf) to load meet, judge, routine information to Supabase to separate tables.

Help me to load the figure results to local hosted Supabase. Here are the 2 PDF files with all details of the figure competition detail:

- `swim-meets/2026/YouthChampionshipand12uinvitational/figure/Summary_-_Youth_Figures.pdf`
- `swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Youth_Figures.pdf`
