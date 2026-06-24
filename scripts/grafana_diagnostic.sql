\set ON_ERROR_STOP on

-- Diagnostic Grafana / PostgreSQL
-- Usage:
--   psql postgresql://pfe_user:12345@localhost:5432/pfe_db -f scripts/grafana_diagnostic.sql
--
-- Default project from your example:
\set project_id '3d962fd2-f260-47dc-861a-23b887f4c7d8'

\echo '=== Project ==='
select id, name, visibility, owner_employee_id, created_at
from projects
where id = :'project_id'::uuid;

\echo '=== Governance: datasets by classification ==='
select coalesce(classification, 'UNKNOWN') as classification,
       count(*)::int as datasets
from datasets
where project_id = :'project_id'::uuid
group by 1
order by datasets desc;

\echo '=== Governance: owners ==='
select coalesce(owner_employee_id, 'UNKNOWN') as owner_employee_id,
       count(*)::int as datasets
from datasets
where project_id = :'project_id'::uuid
group by 1
order by datasets desc;

\echo '=== Pipeline: dag runs by status ==='
select date_trunc('day', dr.created_at) as day,
       coalesce(dr.status, 'unknown') as status,
       count(*)::int as runs
from dag_runs dr
join datasets d on d.id = dr.dataset_id
where d.project_id = :'project_id'::uuid
group by 1, 2
order by 1, 2;

\echo '=== Pipeline: recent run durations (ms) ==='
select dr.id,
       dr.dag_run_id,
       dr.status,
       dr.created_at,
       extract(epoch from (coalesce(dr.updated_at, now()) - dr.created_at)) * 1000.0 as duration_ms
from dag_runs dr
join datasets d on d.id = dr.dataset_id
where d.project_id = :'project_id'::uuid
  and dr.created_at is not null
order by dr.created_at desc
limit 20;

\echo '=== Lineage: push history by status ==='
select date_trunc('day', ph.pushed_at) as day,
       coalesce(ph.status, 'unknown') as status,
       count(*)::int as pushes
from push_history ph
join datasets d on d.id = ph.dataset_id
where d.project_id = :'project_id'::uuid
group by 1, 2
order by 1, 2;

\echo '=== Lineage: recent pushes ==='
select ph.id,
       ph.dataset_id,
       ph.status,
       ph.pushed_at,
       ph.parent_found,
       ph.similarity_score,
       ph.execution_time_ms
from push_history ph
join datasets d on d.id = ph.dataset_id
where d.project_id = :'project_id'::uuid
order by ph.pushed_at desc
limit 20;

\echo '=== Quality: checks by status ==='
select date_trunc('day', dqr.created_at) as day,
       coalesce(upper(dqr.status), 'UNKNOWN') as status,
       count(*)::int as checks
from data_quality_results dqr
join dataset_versions dv on dv.id = dqr.dataset_version_id
join datasets d on d.id = dv.dataset_id
where d.project_id = :'project_id'::uuid
group by 1, 2
order by 1, 2;

\echo '=== Quality: recent anomalies ==='
select d.name as dataset,
       dqr.validator_name,
       dqr.check_type,
       coalesce(dqr.column_name, '-') as column_name,
       dqr.status,
       coalesce(dqr.error_count, 0) as error_count,
       dqr.ratio,
       dqr.created_at
from data_quality_results dqr
join dataset_versions dv on dv.id = dqr.dataset_version_id
join datasets d on d.id = dv.dataset_id
where d.project_id = :'project_id'::uuid
  and dqr.created_at >= now() - interval '30 days'
  and upper(dqr.status) <> 'SUCCESS'
order by dqr.created_at desc
limit 50;
