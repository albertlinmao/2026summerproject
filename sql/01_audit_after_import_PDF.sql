// 01 - check Events after import of PDF data
SELECT * FROM public.as_event
ORDER BY id ASC 

// Events: before and after import of PDF data, to verify that the import was successful and that the data is consistent.
// Date: 2026-07-23
// event_id = 'ab00c602-52cb-435c-96e0-66df6854ac60'

// 02 - check the new data into the as_meet table
SELECT * FROM public.as_meet
WHERE event_id = 'REPLACE_WITH_EVENT_ID_FROM_STEP01'
ORDER BY id ASC 

SELECT * FROM public.as_meet
WHERE event_id = 'ab00c602-52cb-435c-96e0-66df6854ac60'
ORDER BY id ASC 

// Date: 2027-07-23
// meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'


// 03 - check the new data into the as_figure table
SELECT * FROM public.as_figure
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_figure
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 


// 04 - check the new data into the as_figure table
SELECT * FROM public.as_meet_judge_panel
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_meet_judge_panel
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 

//
// 05 - check the meet results
//
// 051 - check the meet/figure results
SELECT * FROM public.as_meet_figure_result
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_meet_figure_result
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 

//
// 052 - check the meet/routine results
SELECT * FROM public.as_meet_routine_result
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_meet_routine_result
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 