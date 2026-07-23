# Prompts to load data from Routine result

## 2026-07-19

Step1: modify table name `as_figure_judge_panel` to `as_meet_judge_panel` , and also modify the field `figure_name` to `panel_name`. And also update `ingest_figures.py` to address the changes.

Step2:
Create `as_meet_routine_result` table to store team/swimmer score in `sql\create_figures_table.sql`

Here is the SQL to create the table

create table if not exists as_meet_routine_result (
id uuid default gen_random_uuid() primary key,
meet_id uuid references as_meet(id) on delete cascade,
rank text,
draw text,
team_code text,
team_name text,
team_athletes jsonb,
total_difficulty jsonb,
routine_scores jsonb,
element_total numeric,
artisticimpression_total numeric,
synchronization_total numeric,
routine_score numeric,
source_file text,
created_at timestamptz default now()
);

Stpe3:
create `scripts\ingest_routines.py` based on `scripts\ingest_figures.py` to use the event and meet if exist in the tables. The existing criteria is the event_name existing in the `as_event` table and/or meet_name existing in the `as_meet`, then use the existing event id / meet id to load the other data from the PDF file.

enhance the script to load data to `as_figure_judge_panel` table from the routine result PDF.

add new rows to import the referee/Asst. Referee/DTC/DATC infomation if show on the PDF. see the sample of part from the PDF, and data structure below

(meet_id, figure_id = null, figure_code_short = null, panel_name = "Referee", panel = {"Referee": "Candy HIPP"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "Asst. Referee", panel = {"Asst. Referee": "Beth MOORE"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "Elements", panel = {"J1": "Karen ROSOLOWSKI", "J2":"Olivia ZHANG", "J3":"Heidi LURENZ", "J4":"Debbie LATCHFORD"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "Artistic Impression", panel = {"J1": "Svetlana MALINOVSKAYA", "J2":"Denise SHIVELY", "J3":"Shannon KORPELA", "J4":"Ginny JASONTEK"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "Synchronization ", panel = {"J1": "Rachael NAESSENS", "J2":"Dana BRADLEY", "J3":"Laura GANZEL"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "DTC", panel = {"DTC": "Chris LEAHY"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "DATC", panel = {"DATC": "Christine MCMASTER-SHAH"}, created_at)
(meet_id, figure_id = null, figure_code_short = null, panel_name = "DATC", panel = {"DATC": "DATC"}, created_at)

```text
                                   Referee: Candy HIPP
                             Asst. Referee: Beth MOORE
       Elements                        Artistic Impression            Synchronization
   J1  Karen ROSOLOWSKI                Svetlana MALINOVSKAYA          Rachael NAESSENS
   J2  Olivia ZHANG                    Denise SHIVELY                 Dana BRADLEY
   J3  Heidi LURENZ                    Shannon KORPELA                Laura GANZEL
   J4  Debbie LATCHFORD                Ginny JASONTEK
                                     DTC: Chris LEAHY
                                    DATC: Christine MCMASTER-SHAH
                                    DATC: Megan LOEHNDORF

```

here are 2 swimmers' score copied from the PDF to map with the data structure to table `as_meet_figure_result`

(id, meet_id,rank=1,draw=17,team_code="WCA",team_name="WALNUT CREEK AQUANUTS",team_athletes="[
{
"name": "DAY Emilia",
"gender": "Female",
"is_reserve": false
},
{
"name": "DUCULESCU Eva",
"gender": "Female",
"is_reserve": false
},
{
"name": "KAPROVSKIY Elizabeth",
"gender": "Female",
"is_reserve": false
},
{
"name": "MIKULICH Dina",
"gender": "Female",
"is_reserve": false
},
{
"name": "NAGY-GALIK Lora",
"gender": "Female",
"is_reserve": false
},
{
"name": "PETROV Katherine",
"gender": "Female",
"is_reserve": false
},
{
"name": "QUALK Katerina",
"gender": "Female",
"is_reserve": false
},
{
"name": "SHEN Averie",
"gender": "Female",
"is_reserve": false
},
{
"name": "BYRUM Dahlia",
"gender": "Female",
"is_reserve": true
},
{
"name": "ZHAO Sunny",
"gender": "Female",
"is_reserve": true
}
]",
total_difficulty=[{"Ref":35.775}, {"DD":35.775}],
routine_scores={
"element_scores": [{
"element_type": "ACRO",
"factor": 0.7,
"dd": 2.65,
"J1": 7.75,
"J2": 7.25,
"J3": 8.5,
"J4": 8.0,
"total": 14.6854
},
{
"element_type": "ACRO",
"factor": 0.7,
"dd": 2.775,
"J1": 9.0,
"J2": 7.25,
"J3": 8.0,
"J4": 7.75,
"total": 15.3781
},
{
"element_type": "HYBRID",
"factor": 0.7,
"dd": 7.0,
"J1": 6.5,
"J2": 6.5,
"J3": 6.75,
"J4": 6.25,
"total": 31.85
},
{
"element_type": "ACRO",
"factor": 0.7,
"dd": 2.35,
"J1": 6.0,
"J2": 7.5,
"J3": 8.0,
"J4": 7.5,
"total": 12.2004
},
{
"element_type": "HYBRID",
"factor": 0.7,
"dd": 7.0,
"J1": 6.25,
"J2": 6.5,
"J3": 6.5,
"J4": 5.5,
"total": 31.0333
},
{
"element_type": "HYBRID",
"factor": 0.7,
"dd": 7.0,
"J1": 5.75,
"J2": 6.25,
"J3": 6.0,
"J4": 6.0,
"total": 29.4
},
{
"element_type": "HYBRID",
"factor": 0.7,
"dd": 7.0,
"J1": 5.75,
"J2": 6.25,
"J3": 6.25,
"J4": 5.75,
"total": 29.4
}
],
"artistic_impression_scores": [
{
"element_type": "Choreo and Music",
"factor": 1.2,
"J1": 7.25,
"J2": 7.0,
"J3": 6.75,
"J4": 7.0,
"total": 25.2
},
{
"element_type": "Performance",
"factor": 1.0,
"J1": 7.0,
"J2": 6.5,
"J3": 6.75,
"J4": 6.75,
"total": 20.25
},
{
"element_type": "Transitions",
"factor": 1.2,
"J1": 6.75,
"J2": 6.5,
"J3": 6.75,
"J4": 6.75,
"total": 24.3
}
],
"synchronization_scores": [
{
"element_type": "STC Small",
"factor": 0.1,
"J1": 38,
"J2": 45,
"J3": 49,
"total": 4.4,
"penalty": -6.9
},
{
"element_type": "STC Obvious",
"factor": 0.5,
"J1": 12,
"J2": 2,
"J3": 1,
"total": 2.5
},
{
"element_type": "STC Major-Median",
"factor": 3.0,
"J1": 0,
"J2": 0,
"J3": 0,
"total": 0.0
}
]  
},
element_total=163.9473,artisticimpression_total=69.7500,synchronization_total=-6.9000, routine_score=226.7973,source_file,created_at);

```text

Code Rank Draw Team             Ref DD    J1   J2   J3   J4     Total Pen.    Total        Routine
     1.   (17) WCA - WALNUT CREEK AQUANUTS
                ACRO (0.7)           2.650 7.75 7.25 8.50 8.00 14.6854       163.9473       226.7973
                ACRO (0.7)           2.775 9.00 7.25 8.00 7.75 15.3781
              HYBRID (0.7)           7.000 6.50 6.50 6.75 6.25 31.8500
                ACRO (0.7)           2.350 6.00 7.50 8.00 7.50 12.2004
              HYBRID (0.7)           7.000 6.25 6.50 6.50 5.50 31.0333
              HYBRID (0.7)           7.000 5.75 6.25 6.00 6.00 29.4000
              HYBRID (0.7)           7.000 5.75 6.25 6.25 5.75 29.4000
          TOTAL DIFFICULTY   35.775 35.775
    Choreo and Music (1.2)                 7.25 7.00 6.75 7.00 25.2000        69.7500
         Performance (1.0)                 7.00 6.50 6.75 6.75 20.2500
         Transitions (1.2)                 6.75 6.50 6.75 6.75 24.3000
           STC Small (0.1)                 38   45   49         4.4000        -6.9000
         STC Obvious (0.5)                 12   2    1          2.5000
    STC Major-Median (3.0)                 0    0    0          0.0000
              F DAY Emilia
              F DUCULESCU Eva
              F KAPROVSKIY Elizabeth
              F MIKULICH Dina
              F NAGY-GALIK Lora
              F PETROV Katherine
              F QUALK Katerina
              F SHEN Averie
              F [R] BYRUM Dahlia
              F [R] ZHAO Sunny



Created using the ISS MMS www.integratedsports.net Printed: 6/29/2026 9:03:30 AM
Page: 1 Licensed to USA Artistic Swimming
Code Rank Draw Team             Ref DD    J1   J2   J3   J4     Total Pen.    Total        Routine
28 JUN 2026
Age Group 12 and Under Team Free Prelims
2026 Junior Olympic Championships
     2.   (25) SCA - SANTA CLARA ARTISTIC SWIMMING
                ACRO (0.7)           2.762 8.50 7.75 8.50 8.00 15.9505       167.3279       226.4946
              HYBRID (0.7)           7.000 6.00 6.50 6.50 6.25 31.0333
              HYBRID (0.7)           7.000 5.75 6.50 6.25 6.25 30.6250
                ACRO (0.7)           2.437 7.75 7.50 7.75 8.00 13.2207
              HYBRID (0.7)           7.000 5.75 6.75 6.25 6.00 30.2167
              HYBRID (0.7)           7.000 5.75 6.25 6.50 6.00 30.2167
                ACRO (0.7)           2.700 9.00 7.00 8.50 8.75 16.0650
          TOTAL DIFFICULTY   35.899 35.899
    Choreo and Music (1.2)                 7.25 7.00 7.25 7.00 25.8000        72.0000
         Performance (1.0)                 7.00 6.50 7.25 7.00 21.0000
         Transitions (1.2)                 6.75 7.00 7.25 7.00 25.2000
           STC Small (0.1)                 27   43   45         3.8333       -12.8333
         STC Obvious (0.5)                 7    7    4          3.0000
    STC Major-Median (3.0)                 2    2    2          6.0000
              F AGASYANTS Mira
              F BIRIK Tutku
              F DUAN Nolannie
              F GAUDET Aurora
              F GUTIERREZ Sofia
              F LI Xiaorong
              F NIMBALKER Sihi
              F ZHOU Yiwei
              F [R] MANSOUR Maya
              F [R] NIEMANN Adalynn

```
