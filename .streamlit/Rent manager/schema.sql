-- Run in Supabase: SQL Editor > New query > paste > Run
create extension if not exists "pgcrypto";

create table properties (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  photo_url text
);

create table units (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  unit_name text not null,
  monthly_rent numeric(12,2) not null default 0
);

create table tenants (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references units(id) on delete cascade,
  full_name text not null,
  phone text,
  monthly_rent numeric(12,2) not null,
  lease_start date,
  lease_end date,
  deposit_amount numeric(12,2) default 0,
  is_active boolean not null default true
);

create table income (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references tenants(id),
  unit_id uuid not null references units(id),
  date_received date not null default current_date,
  amount numeric(12,2) not null check (amount > 0),
  payment_method text not null check (payment_method in ('Cash','EFT','Card')),
  for_month date not null default date_trunc('month', current_date),
  notes text
);

create table expense_categories (
  id serial primary key,
  name text not null unique,
  icon text
);

create table expenses (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id),
  unit_id uuid references units(id),
  category_id int not null references expense_categories(id),
  date date not null default current_date,
  amount numeric(12,2) not null check (amount > 0),
  description text,
  receipt_url text
);

insert into expense_categories (name, icon) values
  ('Repairs & Maintenance','🔧'), ('Rates & Taxes','🏛️'),
  ('Water/Electricity','💡'), ('Insurance','🛡️'),
  ('Levies','🏢'), ('Other','📦');

create index on income (date_received);
create index on expenses (date);

-- "Who hasn't paid this month": active tenants with no income for the current month
create view unpaid_this_month as
select t.id as tenant_id, t.full_name, u.unit_name, p.name as property_name, t.monthly_rent
from tenants t
join units u on u.id = t.unit_id
join properties p on p.id = u.property_id
where t.is_active
  and not exists (
    select 1 from income i
    where i.tenant_id = t.id
      and i.for_month = date_trunc('month', current_date)::date
  );
