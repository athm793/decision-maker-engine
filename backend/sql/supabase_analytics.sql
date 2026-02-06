drop view if exists public.user_analytics;

create view public.user_analytics as
select
  p.id as user_id,
  p.email,
  p.work_email,
  p.first_name,
  p.last_name,
  p.company_name,
  p.role,
  p.signup_ip,
  p.last_ip,
  p.last_seen_at,
  p.created_at,
  coalesce(s.plan_key, 'free') as subscription_plan_key,
  s.status as subscription_status,
  s.current_period_end,
  s.provider as subscription_provider,
  coalesce(ca.balance, 0) as credits_balance,
  coalesce(j.job_count, 0) as job_count,
  coalesce(j.last_job_at, null) as last_job_at,
  coalesce(j.total_companies, 0) as total_companies,
  coalesce(j.processed_companies, 0) as processed_companies,
  coalesce(j.decision_makers_found, 0) as decision_makers_found,
  coalesce(j.credits_spent, 0) as credits_spent,
  coalesce(j.total_cost_usd, 0) as total_cost_usd,
  coalesce(j.llm_calls_started, 0) as llm_calls_started,
  coalesce(j.llm_calls_succeeded, 0) as llm_calls_succeeded,
  coalesce(j.serper_calls, 0) as serper_calls,
  coalesce(j.llm_total_tokens, 0) as llm_total_tokens
from public.profiles p
left join public.subscriptions s on s.user_id = p.id
left join public.credit_accounts ca on ca.user_id = p.id
left join (
  select
    user_id,
    count(*)::int as job_count,
    max(created_at) as last_job_at,
    coalesce(sum(total_companies), 0)::int as total_companies,
    coalesce(sum(processed_companies), 0)::int as processed_companies,
    coalesce(sum(decision_makers_found), 0)::int as decision_makers_found,
    coalesce(sum(credits_spent), 0)::int as credits_spent,
    coalesce(sum(total_cost_usd), 0)::float8 as total_cost_usd,
    coalesce(sum(llm_calls_started), 0)::int as llm_calls_started,
    coalesce(sum(llm_calls_succeeded), 0)::int as llm_calls_succeeded,
    coalesce(sum(serper_calls), 0)::int as serper_calls,
    coalesce(sum(llm_total_tokens), 0)::int as llm_total_tokens
  from public.jobs
  group by user_id
) j on j.user_id = p.id;

create or replace function public.admin_adjust_credits(
  p_user_id text,
  p_delta integer,
  p_reason text default null,
  p_expires_days integer default null
)
returns integer
language plpgsql
security definer
as $$
declare
  v_balance integer;
  v_source text;
  v_lot_id text;
  v_expires_at timestamptz;
begin
  if p_user_id is null or length(btrim(p_user_id)) = 0 then
    raise exception 'Invalid user_id';
  end if;

  if p_delta is null or p_delta = 0 then
    select coalesce(balance, 0) into v_balance from public.credit_accounts where user_id = p_user_id;
    return coalesce(v_balance, 0);
  end if;

  v_source := 'sql_admin_adjust:' || md5(random()::text || clock_timestamp()::text);
  if p_delta > 0 then
    v_lot_id := md5(random()::text || clock_timestamp()::text);
    if p_expires_days is not null and p_expires_days > 0 then
      v_expires_at := now() + make_interval(days => p_expires_days);
    else
      v_expires_at := null;
    end if;
  else
    v_lot_id := null;
    v_expires_at := null;
  end if;

  insert into public.credit_ledger (user_id, lot_id, event_type, delta, source, job_id, expires_at, metadata)
  values (
    p_user_id,
    v_lot_id,
    'admin_adjust',
    p_delta,
    v_source,
    null,
    v_expires_at,
    case when p_reason is null then null else jsonb_build_object('reason', p_reason) end
  );

  insert into public.credit_accounts (user_id, balance, updated_at)
  values (p_user_id, 0, now())
  on conflict (user_id) do nothing;

  update public.credit_accounts
  set balance = coalesce(balance, 0) + p_delta,
      updated_at = now()
  where user_id = p_user_id
  returning balance into v_balance;

  return coalesce(v_balance, 0);
end;
$$;
