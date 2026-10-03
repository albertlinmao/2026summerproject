-- ============================================================================
-- 02 - clear every club-scoped row for one club, selected by club id
-- ============================================================================
--
-- Usage: Supabase SQL editor or psql against the project's DB. Edit the two
-- settings in section 0, read the preview, then re-run with apply = 'yes'.
--
--   select id, code, name from public.as_club order by name;
--
-- Everything happens in one transaction, and nothing is deleted unless
-- clear_club.apply = 'yes'. A default run prints the preview, reports that it
-- stopped, and commits nothing.
--
-- ---------------------------------------------------------------------------
-- SCOPE: what this deletes
-- ---------------------------------------------------------------------------
-- A club IS a tenant. `as_club.id = tenant.id` (design 002 section 4.1), so one
-- club id addresses both sides of the mirror and both are cleared together.
--
--   Dashboard, club-scoped:
--     as_video_uploads                      (cascades to as_video_markers)
--     as_routine_timers
--     as_competition_results_browser_widgets
--     as_person_link                        (guardian edges inside the club)
--     as_team                               (cascades to as_team_member)
--     as_club_membership                    (the authorization edge)
--     as_club                               (the mirror; deleted last)
--   User service, keyed by the same id:
--     membership, role (cascades to role_permission), tenant_api_keys, tenant
--
-- Delete order is not cosmetic. `as_video_uploads`, `as_routine_timers` and
-- `as_competition_results_browser_widgets` reference as_club with no ON DELETE
-- action, so they refuse the row until they are removed first. `as_team`
-- references tenant(id) rather than as_club(id), so it is never cascaded by the
-- club delete and has to be named explicitly.
--
-- ---------------------------------------------------------------------------
-- OUT OF SCOPE: what this does NOT delete, and why
-- ---------------------------------------------------------------------------
-- Competition records -- as_event, as_meet, as_figure, as_meet_judge_panel,
--   as_meet_figure_result, as_meet_routine_result.
--   These are imported official results. The constitution requires that official
--   results are never modified after publication (corrections are amendment
--   records, not overwrites), and none of them carries a club_id: a result row
--   knows its club only as the transcribed text `team_code` / `team_name`.
--   Deleting "this club's results" would mean matching on that text, which is a
--   guess about identity rather than a foreign key. Left alone deliberately.
--
-- audit_log.
--   Immutable by constitution, and it has no club column -- it is filtered by
--   `table_name` / `record_id`, so "this club's audit rows" is not a question
--   this script can answer. Rows naming a deleted person are not touched either:
--   `audit_log.changed_by` is ON DELETE SET NULL, and an audit trail is expected
--   to outlive the subjects it describes.
--
-- as_person / as_person_identity -- kept by default, purge is opt-in (section 4).
--   A person belongs to no club; membership is the edge (identity-contract.md).
--   One person may hold memberships in several clubs, so a purge keyed on this
--   club alone would be wrong. It is also not cheap: deleting as_person cascades
--   into as_result_person_link, as_coaching_recommendations and
--   as_predictive_insights, and is refused outright by as_competition_result
--   (no ON DELETE action). Section 4 therefore only purges persons this club
--   held and who, afterwards, hold no membership anywhere.
--
-- user_profile and auth.users.
--   An account is not club data -- it is how a person logs in to any of their
--   clubs, so it is NOT cleared by default. Section 5 deletes the auth accounts
--   this club alone was holding, and that is opt-in because it is the one
--   deletion in this script that cannot be undone by re-importing a PDF.
--
--   Why opt-in rather than simply out of scope: an account outlives its club, so
--   a purge keyed on this club can only be correct for a subject who afterwards
--   holds no membership anywhere. Section 5 re-checks that at delete time rather
--   than trusting the preview, and refuses anyone still referenced elsewhere.
--
--   Section 5 also destroys the user_profile row, because user_profile.id is a
--   foreign key to auth.users(id) declared ON DELETE CASCADE. That is the
--   encrypted PII going with it. The identity service's stated GDPR approach is to
--   scrub PII in place rather than drop the row, so that the UUID keeps resolving
--   inside historical audit records; section 5 therefore exists for teardown of a
--   club that is genuinely finished, and for GDPR erasure requests. To satisfy
--   GDPR without losing the row, do not use section 5 -- scrub through the
--   identity service, which keeps auth.users and rewrites the profile in place.
--
-- as_daily_aggregations is a materialized view over meet results, not a club
-- table. It is refreshed in section 7 rather than deleted.
--
-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
-- RLS is enabled on most of these tables but not FORCE'd, so a run as the table
-- owner (`postgres`, the local stack's default) bypasses it. Run as any other
-- role and the policies apply, and the deletes match no rows.
-- ============================================================================

begin;


-- ---------------------------------------------------------------------------
-- 0. PARAMETERS
-- ---------------------------------------------------------------------------

-- 'no' prints the preview and deletes nothing. 'yes' performs the deletes.
select set_config('clear_club.apply', 'yes', true);

-- Purge the persons this club held, if they hold no other membership. Read
-- section 4 before switching this on.
select set_config('clear_club.purge_people', 'yes', true);

-- Delete the auth accounts those people held, if they hold no other membership.
-- Off by default. Read section 5 before switching this on: it is the only
-- deletion here that destroys an encrypted user_profile row as a side effect.
select set_config('clear_club.purge_auth_users', 'no', true);

-- The club to clear. This is the only place in the script the id is written;
-- everything below reads it back out of _clear_club_ctx.
create temporary table _clear_club_ctx (
    club_id     uuid primary key,
    club_name   text,
    club_code   text,
    tenant_name text
) on commit drop;

insert into _clear_club_ctx (club_id, club_name, club_code, tenant_name)
select c.id, c.name, c.code, t.name
from public.as_club c
left join public.tenant t on t.id = c.id
where c.id = 'cac7197f-d8fb-4086-ada5-e416c968549c'::uuid;


-- ---------------------------------------------------------------------------
-- 1. VERIFY
--    Stops on an unknown or mistyped id rather than deleting whatever a bad
--    edit happened to match. An invalid uuid literal fails here too, which is
--    the intended way to find out.
-- ---------------------------------------------------------------------------
do $$
declare
    matched int;
begin
    select count(*) into matched from _clear_club_ctx;
    if matched = 0 then
        raise exception
            'no as_club row for the id in section 0. Run: select id, code, name from public.as_club order by name;';
    end if;
end
$$;

select 'TARGET' as step, club_id, club_name, club_code, tenant_name
from _clear_club_ctx;

-- The people this club was holding, captured here because section 3 deletes the
-- membership rows that identify them: afterwards the set is no longer
-- recoverable from as_club_membership, and section 4 would find nobody.
create temporary table _clear_club_people on commit drop as
select distinct m.person_id
from public.as_club_membership m
join _clear_club_ctx c on c.club_id = m.club_id;

-- The auth subject ids behind those people, captured at the same moment and for
-- the same reason, with one more: section 4 deletes as_person, which cascades to
-- as_person_identity, so after it runs there is nothing left to read subject ids
-- from and section 5 would have nothing to act on. Captured here, section 5 acts
-- later.
--
-- as_person_identity is absent for a person with no login (identity-contract.md),
-- so the left join is the normal case for a seeded roster, not an error. A person
-- who somehow holds several identities contributes every subject id; section 5
-- re-checks each one individually.
create temporary table _clear_club_subjects on commit drop as
select distinct pi.subject_id
from _clear_club_people cp
join public.as_person_identity pi on pi.person_id = cp.person_id
where pi.subject_id is not null;


-- ---------------------------------------------------------------------------
-- 2. PREVIEW
--    Always runs, before anything is deleted, and is the reason to run the
--    script with apply = 'no' first.
-- ---------------------------------------------------------------------------
with p as (select club_id from _clear_club_ctx),
counts as (
    select 'as_video_uploads' as label, count(*) as rows
    from public.as_video_uploads v, p where v.club_id = p.club_id
    union all
    select 'as_video_markers (via as_video_uploads)', count(*)
    from public.as_video_markers vm
    join public.as_video_uploads u on u.id = vm.video_id, p
    where u.club_id = p.club_id
    union all
    select 'as_routine_timers', count(*) from public.as_routine_timers t, p where t.club_id = p.club_id
    union all
    select 'as_competition_results_browser_widgets', count(*)
    from public.as_competition_results_browser_widgets w, p where w.club_id = p.club_id
    union all
    select 'as_person_link', count(*) from public.as_person_link l, p where l.club_id = p.club_id
    union all
    select 'as_team', count(*) from public.as_team t, p where t.club_id = p.club_id
    union all
    select 'as_team_member (via as_team)', count(*)
    from public.as_team_member tm
    join public.as_team t on t.id = tm.team_id, p
    where t.club_id = p.club_id
    union all
    select 'as_club_membership', count(*) from public.as_club_membership m, p where m.club_id = p.club_id
    union all
    select 'as_club', count(*) from public.as_club c1, p where c1.id = p.club_id
    union all
    select 'membership', count(*) from public.membership m, p where m.tenant_id = p.club_id
    union all
    select 'role_permission (via role)',
           (select count(*) from public.role_permission rp
              join public.role r on r.id = rp.role_id, p
            where r.tenant_id = p.club_id)
    union all
    select 'role', count(*) from public.role r, p where r.tenant_id = p.club_id
    union all
    select 'tenant_api_keys', count(*) from public.tenant_api_keys k, p where k.tenant_id = p.club_id
    union all
    select 'tenant', count(*) from public.tenant tn, p where tn.id = p.club_id
)
select label as "WOULD DELETE", rows from counts where rows > 0 order by rows desc, label;

-- Persons section 4 would consider, and how many would survive the club.
-- Asked as "does this person hold a membership somewhere ELSE", because before
-- the deletes every one of them still holds one here -- asking whether they
-- hold any membership at all would answer 0 for all of them, every time.
-- Reads the set captured in section 1, so this and section 4 count the same
-- people.
with p as (select club_id from _clear_club_ctx),
elsewhere as (
    select distinct m.person_id
    from public.as_club_membership m, p
    where m.club_id <> p.club_id
)
select 'persons this club held' as metric, count(*) as value from _clear_club_people
union all
select 'of those, also in another club (kept either way)',
       (select count(*) from _clear_club_people
         where person_id in (select person_id from elsewhere))
union all
select 'of those, held only by this club (section 4 would purge)',
       (select count(*) from _clear_club_people
         where person_id not in (select person_id from elsewhere));

-- Accounts section 5 would delete, split by whether they are safe to delete.
-- Asked as "is this subject still referenced somewhere", because a subject is
-- only ever *this* club's to remove once nothing else points at it.
--
-- Both branches EXCLUDE the club being cleared. This preview runs before
-- section 3, so this club's own membership rows are still present; without the
-- exclusion every subject would look "referenced elsewhere" and section 5 would
-- be reported as deleting nothing. Same exclusion style as the person counts
-- above, for the same reason. Section 5 re-checks with no club filter at all,
-- because by the time it runs section 3 has already removed this club's rows.
with elsewhere_subjects as (
    -- Reachable from any person holding any membership, in another club.
    select distinct pi.subject_id
    from public.as_club_membership m2
    join public.as_person_identity pi on pi.person_id = m2.person_id,
         _clear_club_ctx c
    where m2.club_id <> c.club_id
    -- ...and from a user-service membership row keyed directly on the subject.
    union
    select distinct m3.user_id
    from public.membership m3, _clear_club_ctx c
    where m3.tenant_id <> c.club_id
)
select 'auth subjects captured for this club' as metric, count(*) as value
from _clear_club_subjects
union all
select 'of those, still referenced elsewhere (section 5 would KEEP)',
       (select count(*) from _clear_club_subjects
         where subject_id in (select subject_id from elsewhere_subjects))
union all
select 'of those, unreferenced (section 5 would DELETE)',
       (select count(*) from _clear_club_subjects
         where subject_id not in (select subject_id from elsewhere_subjects))
union all
select 'user_profile rows that would be destroyed by cascade',
       (select count(*) from _clear_club_subjects s
         where s.subject_id not in (select subject_id from elsewhere_subjects)
           and exists (select 1 from public.user_profile p where p.id = s.subject_id))
union all
select 'auth.identities rows that would be destroyed by cascade',
       (select count(*) from _clear_club_subjects s
         where s.subject_id not in (select subject_id from elsewhere_subjects)
           and exists (select 1 from auth.identities i where i.user_id = s.subject_id));


-- ---------------------------------------------------------------------------
-- 3. APPLY
--    The gate. With apply = 'no' this is the only thing that runs, and it says
--    so out loud rather than failing silently.
-- ---------------------------------------------------------------------------
do $$
declare
    target uuid;
begin
    if current_setting('clear_club.apply', true) is distinct from 'yes' then
        raise notice 'PREVIEW ONLY - nothing deleted. Set clear_club.apply to yes in section 0 to apply.';
        return;
    end if;

    select club_id into target from _clear_club_ctx;

    -- Order matters; see the header. Each statement is scoped to the one club.

    delete from public.as_video_uploads u
     using _clear_club_ctx c where u.club_id = c.club_id;   -- cascades as_video_markers

    delete from public.as_routine_timers t
     using _clear_club_ctx c where t.club_id = c.club_id;

    delete from public.as_competition_results_browser_widgets w
     using _clear_club_ctx c where w.club_id = c.club_id;

    delete from public.as_person_link l
     using _clear_club_ctx c where l.club_id = c.club_id;

    delete from public.as_team t
     using _clear_club_ctx c where t.club_id = c.club_id;   -- cascades as_team_member

    delete from public.as_club_membership m
     using _clear_club_ctx c where m.club_id = c.club_id;

    -- User-service side. Same id: a club is a tenant.
    delete from public.membership m
     using _clear_club_ctx c where m.tenant_id = c.club_id;
    delete from public.role r
     using _clear_club_ctx c where r.tenant_id = c.club_id;   -- cascades role_permission
    delete from public.tenant_api_keys k
     using _clear_club_ctx c where k.tenant_id = c.club_id;
    delete from public.tenant t
     using _clear_club_ctx c where t.id = c.club_id;

    -- The mirror last: everything above that references it is already gone.
    delete from public.as_club c1
     using _clear_club_ctx c2 where c1.id = c2.club_id;

    raise notice 'cleared club %', target;
end
$$;


-- ---------------------------------------------------------------------------
-- 4. OPTIONAL: purge the persons this club was holding
--    Off unless clear_club.purge_people = 'yes'. Read this before using it.
--
--    Only persons who, once this club's membership rows are gone, hold no
--    membership in ANY club. A person with another club is never touched, which
--    is the whole point: a person belongs to no club.
--
--    Consequences, all deliberate:
--      * as_person_identity cascades, so the login that reached the person via
--        `sub` no longer resolves. The auth account and its user_profile row
--        stay, so the person can be re-linked; the link is what is lost. Unless
--        section 5 is also switched on, which removes the account too.
--      * as_result_person_link, as_coaching_recommendations and
--        as_predictive_insights cascade with the person, so a person who also
--        appears in imported competition results loses those links.
--      * as_competition_result.person_id has no ON DELETE action, so a person
--        referenced there aborts the statement. Nothing is left half-done: it
--        is atomic, and the failure rolls back section 3 with it.
-- ---------------------------------------------------------------------------
do $$
declare
    purged int;
begin
    if current_setting('clear_club.purge_people', true) is distinct from 'yes' then
        raise notice 'persons kept. Set clear_club.purge_people to yes to purge the unshared ones.';
        return;
    end if;

    delete from public.as_person p
     using _clear_club_people cp
     where p.id = cp.person_id
       and not exists (
           select 1 from public.as_club_membership m where m.person_id = p.id
       );

    get diagnostics purged = row_count;
    raise notice 'purged % person row(s) holding no remaining membership', purged;
end
$$;


-- ---------------------------------------------------------------------------
-- 5. OPTIONAL: purge the auth accounts those people held
--    Off unless clear_club.purge_auth_users = 'yes'. Read this before using it.
--
--    Independent of section 4. It deletes an account whose subject holds no
--    membership in ANY club after section 3 has run, whether or not the person
--    row survived. A person left with no membership and no account is a valid
--    state in this model (a login is optional, design.md 1.1), so the two gates
--    are answered independently on purpose.
--
--    What cascades, and why this is opt-in:
--      * user_profile -- ON DELETE CASCADE from auth.users(id). This is the
--        encrypted PII (email, given name, family name) being destroyed. It is
--        not recoverable: the rows are encrypted, so there is nothing to export
--        first from this script alone.
--      * auth.identities -- CASCADE. For a seeded roster this is the single
--        "email" identity created by scripts/user_mgmt_sync.py.
--      * auth.sessions, auth.refresh_tokens, auth.mfa_factors,
--        auth.one_time_tokens, auth.oauth_authorizations, auth.oauth_consents --
--        all CASCADE, so nobody is left holding a live session for a deleted
--        subject.
--      * as_person_identity -- NOT cascaded by this delete, but already gone if
--        section 4 ran. If section 4 did not run, the person keeps a
--        as_person_identity row pointing at a subject_id that no longer exists.
--        That is harmless for RLS (auth.uid() returns NULL and matches no rows,
--        rather than erroring) but it is a dangling edge, so run section 4 too if
--        you want the graph closed.
--
--    Deliberately NOT done here:
--      * No password is read, logged or restored. encrypted_password is a bcrypt
--        hash and is deleted unread; there is no way back to the plaintext.
--      * No UPDATE instead of DELETE. A "disable" is `user_profile.status =
--        'SUSPENDED'` or `as_club_membership.status = 'left'`, and both are
--        single-row updates the identity service can do without this script.
--      * No mass disable. One subject refusing to delete because a membership
--        row elsewhere still names it must not cascade into disabling every other
--        account on the list.
--
--    Why the safety check is repeated here and not trusted from the preview: the
--    preview ran before section 3, so it could only see memberships as they were
--    before the deletes. Between then and here nothing else in this transaction
--    adds memberships, but the check is cheap and the failure mode -- deleting
--    somebody's only login to a different club -- is not recoverable by re-running.
-- ---------------------------------------------------------------------------
do $$
declare
    removed int;
    kept int;
begin
    if current_setting('clear_club.purge_auth_users', true) is distinct from 'yes' then
        raise notice 'auth accounts kept. Set clear_club.purge_auth_users to yes to delete them.';
        return;
    end if;

    -- Reported, not deleted: these subjects are still named by a membership
    -- somewhere other than this club, so the account is not ours to remove.
    select count(*) into kept
    from _clear_club_subjects s
    where exists (
        select 1
        from public.as_club_membership m2
        join public.as_person_identity pi on pi.person_id = m2.person_id
        where pi.subject_id = s.subject_id
    )
    or exists (
        select 1 from public.membership m3 where m3.user_id = s.subject_id
    );

    if kept > 0 then
        raise notice
            'kept % auth account(s) still referenced by a membership elsewhere -- see the section 2 preview',
            kept;
    end if;

    delete from auth.users u
     using _clear_club_subjects s
     where u.id = s.subject_id
       -- Re-checked per row: a person may hold several identities, and only the
       -- unreferenced ones may go.
       and not exists (
           select 1
           from public.as_club_membership m2
           join public.as_person_identity pi on pi.person_id = m2.person_id
           where pi.subject_id = u.id
       )
       and not exists (
           select 1 from public.membership m3 where m3.user_id = u.id
       );

    get diagnostics removed = row_count;
    raise notice
        'deleted % auth account(s); the same number of user_profile row(s) were destroyed by cascade',
        removed;
end
$$;


-- ---------------------------------------------------------------------------
-- 6. POST-CHECK
--    A cleared club leaves no trace in the club-scoped tables, so after an apply
--    this returns no rows at all. as_person and the competition records are
--    expected to remain -- see the header.
-- ---------------------------------------------------------------------------
select 'LEFTOVER CHECK' as step,
       case when current_setting('clear_club.apply', true) = 'yes'
            then 'apply ran - anything listed here is a bug'
            else 'preview only - present because nothing was deleted'
       end as mode,
       t."table", t.remaining
from (values
    ('as_club',                    (select count(*) from public.as_club c1, _clear_club_ctx c2 where c1.id = c2.club_id)),
    ('as_club_membership',         (select count(*) from public.as_club_membership m, _clear_club_ctx c where m.club_id = c.club_id)),
    ('as_person_link',             (select count(*) from public.as_person_link l, _clear_club_ctx c where l.club_id = c.club_id)),
    ('as_team',                    (select count(*) from public.as_team tm, _clear_club_ctx c where tm.club_id = c.club_id)),
    ('as_video_uploads',           (select count(*) from public.as_video_uploads u, _clear_club_ctx c where u.club_id = c.club_id)),
    ('as_routine_timers',          (select count(*) from public.as_routine_timers r, _clear_club_ctx c where r.club_id = c.club_id)),
    ('as_competition_results_browser_widgets',
                                   (select count(*) from public.as_competition_results_browser_widgets w, _clear_club_ctx c where w.club_id = c.club_id)),
    ('tenant',                     (select count(*) from public.tenant tn, _clear_club_ctx c where tn.id = c.club_id)),
    ('membership',                 (select count(*) from public.membership m, _clear_club_ctx c where m.tenant_id = c.club_id)),
    ('tenant_api_keys',            (select count(*) from public.tenant_api_keys k, _clear_club_ctx c where k.tenant_id = c.club_id)),
    -- Section 5 rows. Expected to be non-zero after an apply ONLY when that
    -- section was switched on and every subject was deletable; listed so a
    -- silent skip is visible rather than inferred from the notice text.
    ('auth.users (section 5)',     (select count(*) from _clear_club_subjects s where exists (select 1 from auth.users u where u.id = s.subject_id))),
    ('user_profile (section 5)',   (select count(*) from _clear_club_subjects s where exists (select 1 from public.user_profile p where p.id = s.subject_id)))
) as t("table", remaining)
where t.remaining > 0;


-- ---------------------------------------------------------------------------
-- 7. REFRESH THE AGGREGATE
--    Read-only over the meet results, which section 3 does not touch, so the
--    numbers are unchanged; refreshed so the view is never left stale by a
--    script someone ran for an unrelated reason.
-- ---------------------------------------------------------------------------
refresh materialized view public.as_daily_aggregations;

commit;
