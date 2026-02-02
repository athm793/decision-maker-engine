import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

let cachedClient = null;
let cachedConfig = null;

export async function loadSupabaseConfig() {
  if (cachedConfig) return cachedConfig;

  if (supabaseUrl && supabaseAnonKey) {
    cachedConfig = { url: supabaseUrl, anonKey: supabaseAnonKey, source: 'build' };
    return cachedConfig;
  }

  try {
    const resp = await fetch('/api/public-config', { headers: { accept: 'application/json' } });
    if (resp.ok) {
      const data = await resp.json();
      const url = String(data?.supabaseUrl || '').trim();
      const anonKey = String(data?.supabaseAnonKey || '').trim();
      if (url && anonKey) {
        cachedConfig = { url, anonKey, source: 'runtime' };
        return cachedConfig;
      }
    }
  } catch (_err) {
  }

  cachedConfig = { url: '', anonKey: '', source: 'missing' };
  return cachedConfig;
}

export async function getSupabaseClient() {
  if (cachedClient) return cachedClient;
  const cfg = await loadSupabaseConfig();
  if (!cfg.url || !cfg.anonKey) return null;
  cachedClient = createClient(cfg.url, cfg.anonKey);
  return cachedClient;
}
