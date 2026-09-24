create table public.profiles (
  id uuid primary key,
  email text not null
);

create table public.notes (
  id bigint generated always as identity primary key,
  body text
);

alter table public.notes enable row level security;
