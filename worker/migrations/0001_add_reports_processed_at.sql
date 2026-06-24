-- Worker Lambda: records when a report has been processed.
--
-- The worker (worker/handler.py -> store.mark_processed) stamps this column for
-- each {region, report_id} message it handles. Apply this once in the Supabase
-- SQL editor (or via psql) BEFORE deploying the worker, otherwise mark_processed
-- fails and messages route to the worker DLQ.
alter table public.reports
    add column if not exists processed_at timestamptz;
