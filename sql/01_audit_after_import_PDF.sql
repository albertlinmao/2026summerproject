// 01 - check Events after import of PDF data
SELECT * FROM public.as_event
ORDER BY id ASC 

DELETE FROM public.as_event

/* Monte Johnson Figure Meet event id: f5632636-b85b-4f96-88c6-3a75763769ab
*/


// Events: before and after import of PDF data, to verify that the import was successful and that the data is consistent.
// Date: 2026-07-23
// event_id = 'f5632636-b85b-4f96-88c6-3a75763769ab'

// 02 - check the new data into the as_meet table
SELECT * FROM public.as_meet
WHERE event_id = 'REPLACE_WITH_EVENT_ID_FROM_STEP01'
ORDER BY id ASC 


SELECT * FROM public.as_meet
WHERE event_id = 'f5632636-b85b-4f96-88c6-3a75763769ab'
ORDER BY id ASC 

SELECT DISTINCT  c.id FROM public.as_meet c
WHERE event_id = 'f5632636-b85b-4f96-88c6-3a75763769ab'

DELETE FROM public.as_meet

/*
"08e887fa-15fa-4ac7-b997-565c3f4746c3"
"22ef2dca-ed68-4ae9-a78f-dc6346a05575"
"47c03e03-701f-4b1b-84ad-991842b04e9f"
"4f87054c-3541-4da0-8db7-6d05cd198d7f"
"61ae13b3-b050-4e5d-83ce-854f67d8af57"
"6a588bb2-51ef-401c-826e-060691c9fcb6"
"76d1a260-3405-43ff-935a-ba5815f0965e"
"88dc2913-120d-49ef-b6b3-47f908a73e38"
"904f6d0e-b1ff-4407-bb15-75eec31b6ae9"
"b3c73ea2-2c38-4988-9d7e-50bcfdf5f659"
"b63f2614-9608-4750-95a6-720f20ece357"
"bbedfe66-c2f9-4f33-8563-b12224dd04bc"
"be7342e0-4296-4bff-aab7-1723b009e7f9"
"cc6ca679-1a46-473e-bbc9-ffa5765f27e8"
"d5ab4b07-19f2-460c-ac5c-3c58113d6c2b"
"dfdc56d5-489f-4a7c-af2c-30ef7083a66c"
"e1d7ae45-c8a6-49ce-a7a0-91c1a886d1b0"
*/



/////////////////////////
// 03 - check the new data into the as_figure table
SELECT * FROM public.as_figure
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_figure
WHERE meet_id = 'e1d7ae45-c8a6-49ce-a7a0-91c1a886d1b0'
ORDER BY id ASC 

DELETE FROM public.as_figure

////////////////////////////////
// 04 - check the new data into the as_meet_judge_panel table

SELECT * FROM public.as_meet_judge_panel
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_meet_judge_panel
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 

DELETE FROM public.as_meet_judge_panel

//////////////////////////
// 05 - check the meet results
//
// 051 - check the meet/figure results

SELECT * FROM public.as_meet_figure_result
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_meet_figure_result
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 



DELETE FROM public.as_meet_figure_result
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'


//
// 052 - check the meet/routine results
SELECT * FROM public.as_meet_routine_result
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'
ORDER BY id ASC 

SELECT * FROM public.as_meet_routine_result
WHERE meet_id = '44734632-5596-40cc-b60a-f57e2b30ab57'
ORDER BY id ASC 


DELETE FROM public.as_meet_routine_result
WHERE meet_id = 'REPLACE_WITH_MEET_ID_FROM_STEP02'