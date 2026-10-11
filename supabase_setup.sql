-- Da eseguire UNA volta in Supabase: SQL Editor -> New query -> incolla -> Run.
create table if not exists public.archivio (
  id integer primary key,
  dati jsonb not null default '{"aziende": []}'::jsonb,
  aggiornato timestamptz not null default now()
);
insert into public.archivio (id) values (1) on conflict (id) do nothing;

-- Nessun accesso pubblico: la tabella si legge e si scrive solo con la chiave «secret» (service_role) dell'app.
alter table public.archivio enable row level security;

-- Bucket privato per gli allegati dei dipendenti
insert into storage.buckets (id, name, public) values ('allegati', 'allegati', false) on conflict (id) do nothing;
