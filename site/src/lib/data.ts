// Build-time access to the JSON files written by the Python pipeline.
// Astro runs this in Node while building, so the finished site is fully static.
import fs from 'node:fs';
import path from 'node:path';

export interface Game {
  appid: number;
  name: string;
  percent_positive: number | null;
  review_count: number | null;
  review_label: string | null;
  release_date?: string | null;
  header_image?: string | null;
  store_url: string;
  price?: string | null;
  is_new_release?: boolean;
}

export interface DropReason {
  code: 'delisted' | 'score_fell' | 'reviews_removed' | 'rating_changed_other';
  detail: string;
  recent_percent_positive?: number;
  summary?: string;
}

export interface Dropped {
  before: Game;
  now: Game | null;
  reason: DropReason;
}

export interface ChangeReport {
  week: string;
  previous_week: string | null;
  total: number;
  new_entries: Game[];
  dropped: Dropped[];
}

export interface Snapshot {
  week: string;
  generated_at: string;
  count: number;
  games: Game[];
}

// OP_DATA_DIR wins; otherwise use ../data once the pipeline has written to it,
// and fall back to the bundled sample data for local development.
function resolveDataDir(): string {
  if (process.env.OP_DATA_DIR) return path.resolve(process.env.OP_DATA_DIR);
  const real = path.resolve('../data');
  if (fs.existsSync(path.join(real, 'current.json'))) return real;
  return path.resolve('sample-data');
}

export const DATA_DIR = resolveDataDir();
export const USING_SAMPLE_DATA = DATA_DIR.endsWith('sample-data');

function readJson<T>(file: string): T | null {
  const full = path.join(DATA_DIR, file);
  return fs.existsSync(full) ? (JSON.parse(fs.readFileSync(full, 'utf8')) as T) : null;
}

export const getCurrent = () => readJson<Snapshot>('current.json');
export const getLatestChanges = () => readJson<ChangeReport>('latest_changes.json');

/** All weekly change reports, newest first. */
export function getAllChanges(): ChangeReport[] {
  const dir = path.join(DATA_DIR, 'changes');
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .sort()
    .reverse()
    .map((f) => readJson<ChangeReport>(path.join('changes', f))!)
    .filter(Boolean);
}

// ---- formatting helpers ----------------------------------------------------

export const formatCount = (n: number | null | undefined) =>
  n == null ? '–' : n.toLocaleString('en-GB');

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  return new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** Prefix an internal path with the site's base (needed on GitHub Pages project sites). */
export function url(p: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${base}/${p.replace(/^\//, '')}`;
}
