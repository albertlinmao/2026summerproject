-- ============================================================================
-- 03 - clear all imported data for one event, selected by event id
-- ============================================================================
--
-- Usage: Supabase SQL editor or psql against the project's DB. Edit the two
-- settings in section 0, read the preview, then re-run with apply = 'yes'.
--
--   select id, event_name, event_date from public.as_event order by event_date;
--
-- Sibling of sql/02_clear_alldata_for_club_using_id.sql and built the same way:
-- one transaction, one gate, a preview that runs whether or not the deletes do.
--
-- ---------------------------------------------------------------------------
-- WHAT THIS IS FOR: RE-IMPORT, NOT PUBLICATION
-- ---------------------------------------------------------------------------
-- The constitution requires that official results are never modified after
-- publication, and that a correction is an amendment record rather than an
-- overwrite. This script deletes result rows outright, so it is a re-import
-- tool: run it on an event you are about to load again from the source PDF, and
-- never on an event that has been published.
--
-- Worth knowing before you rely on the schema to stop you: the guard it does
-- provide is `forbid_result_updates()`, a BEFORE UPDATE trigger on
-- as_meet_figure_result and as_meet_routine_result whose message is "Competition
-- results are immutable; re-import from source PDF instead". That is exactly
-- the workflow this script serves -- and it fires on UPDATE only. A DELETE is
-- not an UPDATE, so nothing in the schema stands between this script and a
-- published event. The precondition above is the only control, which is why it
-- is stated here rather than left to the reader to infer.
--
-- ---------------------------------------------------------------------------
-- SCOPE: one statement does the tree, plus one that the schema cannot do
-- ---------------------------------------------------------------------------
-- The subtree is a clean cascade, so no delete ordering is needed:
--
--   as_event
--     └─ as_meet                        ON DELETE CASCADE  (as_meet.event_id)
--          ├─ as_figure                 ON DELETE CASCADE  (as_figure.meet_id)
--          │    └─ as_meet_judge_panel   ON DELETE CASCADE  (judge panel.figure_id)
--          ├─ as_meet_judge_panel        ON DELETE CASCADE  (judge panel.meet_id)
--          ├─ as_meet_figure_result      ON DELETE CASCADE
--          └─ as_meet_routine_result     ON DELETE CASCADE
--
-- `delete from public.as_event where id = ...` therefore takes the whole subtree
-- with it. That is the opposite of the club script, where three tables reference
-- as_club with no ON DELETE action and had to be named one by one.
--
-- What the schema CANNOT do is clean up as_result_person_link. That table maps an
-- imported result row to a canonical person, but it does it polymorphically:
--
--   result_table text, result_id uuid, person_id uuid, athlete_name text
--   unique (result_table, result_id, athlete_name)   -- an index, not a foreign key
--
-- There is no foreign key from it to either result table, so deleting the results
-- does NOT remove the links. They would survive pointing at result ids that no
-- longer exist, which is wrong in three separate ways:
--   * as_daily_aggregations joins on (result_table, result_id), so a stale link
--     that happens to collide would silently re-attach to a different row;
--   * the link's person_id holds a CASCADE foreign key onto as_person, so a dead
--     link keeps a person alive that no result justifies any more - which later
--     defeats the club script's person purge;
--   * a re-import mints new result ids, so the link can never match again. It is
--     dead weight that nothing will ever clean up.
--
-- So section 1 captures the ids of this event's result rows before the cascade,
-- and section 3 deletes the matching links explicitly, first.
--
-- ---------------------------------------------------------------------------
-- OUT OF SCOPE: what this does NOT delete, and why
-- ---------------------------------------------------------------------------
-- as_result_person_link rows for results OUTSIDE this event. Deleting the event
-- does not invalidate them, so they stay. Section 3 only removes links whose
-- result row is going away in the same transaction.
--
-- as_person, as_person_identity, as_club_membership.
--   A person belongs to no club and is not owned by an event; the imported rows
--   carry only the transcribed `athlete_name`. Whoever this event's swimmers are
--   stays whoever they were. Use sql/02_clear_alldata_for_club_using_id.sql for
--   the club side.
--
-- as_predictive_insights, as_coaching_recommendations.
--   Person-scoped with no meet_id, event_id or date column
--   (id, person_id, next_score_prediction, plateau_risk, ...). There is no key
--   that could scope them to this event, so this script cannot touch them even
--   in principle. Their numbers may well have been computed from the results
--   being deleted and will now be stale; regenerating them is the ML service's
--   job, not this script's.
--
-- as_competition_result.
--   Also person-scoped (person_id, score, date) and not reachable from an event.
--
-- audit_log.
--   Immutable by constitution, and carries no event column - it is filtered by
--   table_name / record_id.
--
-- RLS: unlike the club script, none of these tables has RLS enabled, so there is
-- no role caveat here and no way for a non-owner to silently delete nothing.
-- ============================================================================

begin;


-- ---------------------------------------------------------------------------
-- 0. PARAMETERS
-- ---------------------------------------------------------------------------

-- 'no' prints the preview and deletes nothing. 'yes' performs the deletes.
select set_config('clear_event.apply', 'no', true);

-- The event to clear. This is the only place in the script the id is written;
-- everything below reads it back out of _clear_event_ctx.
create temporary table _clear_event_ctx (
    event_id    uuid primary key,
    event_name  text,
    event_date  date,
    host_city   text,
    meet_count  integer
) on commit drop;

insert into _clear_event_ctx (event_id, event_name, event_date, host_city, meet_count)
select e.id, e.event_name, e.event_date, e.host_city,
       (select count(*)::integer from public.as_meet m where m.event_id = e.id)
from public.as_event e
where e.id = 'REPLACE_WITH_EVENT_ID'::uuid;


-- ---------------------------------------------------------------------------
-- 1. VERIFY AND CAPTURE
--    The verify stops on an unknown or mistyped id rather than deleting whatever
--    a bad edit matched. The capture is the part the schema cannot reconstruct
--    later, so it happens here, before anything is deleted.
-- ---------------------------------------------------------------------------
do $$
declare
    matched int;
begin
    select count(*) into matched from _clear_event_ctx;
    if matched = 0 then
        raise exception
            'no as_event row for the id in section 0. Run: select id, event_name, event_date from public.as_event order by event_date;';
    end if;
end
$$;

select 'TARGET' as step, event_id, event_name, event_date, host_city, meet_count
from _clear_event_ctx;

-- The result ids the cascade is about to destroy, and which as_result_person_link
-- points at by (result_table, result_id). The two literals are not free text:
-- they are the same values as_daily_aggregations matches on.
create temporary table _clear_event_result_ids on commit drop as
select 'as_meet_figure_result'::text as result_table, r.id as result_id
from public.as_meet_figure_result r
join public.as_meet m on m.id = r.meet_id
join _clear_event_ctx c on c.event_id = m.event_id
union all
select 'as_meet_routine_result'::text, r.id
from public.as_meet_routine_result r
join public.as_meet m on m.id = r.meet_id
join _clear_event_ctx c on c.event_id = m.event_id;


-- ---------------------------------------------------------------------------
-- 2. PREVIEW
--    Always runs, before anything is deleted, and is the reason to run the
--    script with apply = 'no' first.
-- ---------------------------------------------------------------------------
with e as (select event_id from _clear_event_ctx),
-- meets and figures are reached through the event, not from each other.
meets as (
    select m.id from public.as_meet m, e where m.event_id = e.event_id
),
counts as (
    select 'as_event' as label, count(*) as rows
    from public.as_event ev, e where ev.id = e.event_id
    union all
    select 'as_meet', count(*) from meets
    union all
    select 'as_figure', count(*)
    from public.as_figure f join meets on meets.id = f.meet_id
    union all
    select 'as_meet_judge_panel', count(*)
    from public.as_meet_judge_panel j join meets on meets.id = j.meet_id
    union all
    select 'as_meet_figure_result', count(*)
    from public.as_meet_figure_result r join meets on meets.id = r.meet_id
    union all
    select 'as_meet_routine_result', count(*)
    from public.as_meet_routine_result r join meets on meets.id = r.meet_id
    union all
    -- Not cascaded by the schema: these point at rows that are about to go.
    select 'as_result_person_link (not cascaded - deleted explicitly)', count(*)
    from public.as_result_person_link l
    join _clear_event_result_ids rid
      on rid.result_table = l.result_table and rid.result_id = l.result_id
)
select label as "WOULD DELETE", rows from counts where rows > 0 order by rows desc, label;

-- The aggregate is a snapshot of the results being deleted. Reporting it tells
-- you what the refresh in section 5 is about to drop.
select 'as_daily_aggregations' as matview, count(*) as rows_before
from public.as_daily_aggregations;


-- ---------------------------------------------------------------------------
-- 3. APPLY
--    The gate. With apply = 'no' this is the only thing that runs, and it says
--    so out loud rather than failing silently.
-- ---------------------------------------------------------------------------
do $$
declare
    target uuid;
begin
    if current_setting('clear_event.apply', true) is distinct from 'yes' then
        raise notice 'PREVIEW ONLY - nothing deleted. Set clear_event.apply to yes in section 0 to apply.';
        return;
    end if;

    select event_id into target from _clear_event_ctx;

    -- First, the links the cascade cannot reach. Doing this before the delete is
    -- what makes them collectable: afterwards the result ids no longer resolve
    -- to anything and there is no way to tell which links were this event's.
    delete from public.as_result_person_link l
     using _clear_event_result_ids rid
     where l.result_table = rid.result_table
       and l.result_id = rid.result_id;

    -- Then the whole subtree in one statement.
    delete from public.as_event ev
     using _clear_event_ctx c
     where ev.id = c.event_id;

    raise notice 'cleared event %', target;
end
$$;


-- ---------------------------------------------------------------------------
-- 4. POST-CHECK
--    A cleared event leaves no trace in the subtree, and no link pointing into it.
--    Persons, predictions and recommendations are expected to remain - see the
--    header.
-- ---------------------------------------------------------------------------
select 'LEFTOVER CHECK' as step,
       case when current_setting('clear_event.apply', true) = 'yes'
            then 'apply ran - anything listed here is a bug'
            else 'preview only - present because nothing was deleted'
       end as mode,
       t."table", t.remaining
from (values
    ('as_event',                 (select count(*) from public.as_event ev, _clear_event_ctx c where ev.id = c.event_id)),
    ('as_meet',                  (select count(*) from public.as_meet m, _clear_event_ctx c where m.event_id = c.event_id)),
    ('as_figure',                (select count(*) from public.as_figure f
                                   join public.as_meet m on m.id = f.meet_id, _clear_event_ctx c where m.event_id = c.event_id)),
    ('as_meet_judge_panel',      (select count(*) from public.as_meet_judge_panel j
                                   join public.as_meet m on m.id = j.meet_id, _clear_event_ctx c where m.event_id = c.event_id)),
    ('as_meet_figure_result',    (select count(*) from public.as_meet_figure_result r
                                   join public.as_meet m on m.id = r.meet_id, _clear_event_ctx c where m.event_id = c.event_id)),
    ('as_meet_routine_result',   (select count(*) from public.as_meet_routine_result r
                                   join public.as_meet m on m.id = r.meet_id, _clear_event_ctx c where m.event_id = c.event_id)),
    ('as_result_person_link',    (select count(*) from public.as_result_person_link l
                                   join _clear_event_result_ids rid
                                     on rid.result_table = l.result_table and rid.result_id = l.result_id))
) as t("table", remaining)
where t.remaining > 0;


-- ---------------------------------------------------------------------------
-- 5. REFRESH THE AGGREGATE
--    as_daily_aggregations is built from as_meet_figure_result and
--    as_meet_routine_result joined to as_meet, so every row derived from this
--    event is now wrong. A plain REFRESH, not REFRESH CONCURRENTLY: CONCURRENTLY
--    cannot run inside a transaction block, and this script is one. The table does
--    carry a unique index on (person_id, date), so moving the refresh outside the
--    transaction would allow CONCURRENTLY if a non-blocking refresh is ever needed.
-- ---------------------------------------------------------------------------
refresh materialized view public.as_daily_aggregations;

commit;