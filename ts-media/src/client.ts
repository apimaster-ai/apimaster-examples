/**
 * Shared setup: credentials, a fetch helper with sane retries, and the polling loop
 * that image and video jobs need.
 *
 * Everything here works against any OpenAI-compatible gateway — only the values in
 * .env change.
 */

export const BASE_URL = (process.env.APIMASTER_BASE_URL ?? 'https://apimaster.ai/v1').replace(/\/+$/, '');

export function apiKey(): string {
  const key = process.env.APIMASTER_API_KEY;
  if (!key) {
    // Failing loudly here is better than sending an empty Authorization header and
    // debugging a 401 that looks like a server problem.
    throw new Error(
      'APIMASTER_API_KEY is not set. Copy .env.example to .env, or export the variable.\n' +
        'Get a key: https://apimaster.ai/docs/getting-started/api-key'
    );
  }
  return key.trim();
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown
  ) {
    const detail =
      typeof body === 'object' && body !== null && 'error' in body
        ? String((body as { error?: { message?: string } }).error?.message ?? '')
        : String(body).slice(0, 200);
    super(`HTTP ${status}${detail ? `: ${detail}` : ''}`);
    this.name = 'ApiError';
  }

  /** 429 and 5xx are worth retrying; 400/401/402 are our fault and never will be. */
  get retryable(): boolean {
    return this.status === 429 || this.status >= 500;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  /** Image generation is slow; the default is deliberately generous. */
  timeoutMs?: number;
  retries?: number;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, timeoutMs = 60_000, retries = 2 } = options;
  const url = path.startsWith('http') ? path : `${BASE_URL}${path}`;

  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${apiKey()}`,
          'Content-Type': 'application/json',
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });

      const text = await response.text();
      let parsed: unknown;
      try {
        parsed = text ? JSON.parse(text) : null;
      } catch {
        parsed = text;
      }
      if (!response.ok) throw new ApiError(response.status, parsed);
      return parsed as T;
    } catch (error) {
      lastError = error;
      const retryable = error instanceof ApiError ? error.retryable : error instanceof Error && error.name === 'TimeoutError';
      if (!retryable || attempt === retries) throw error;
      const backoff = 500 * 2 ** attempt + Math.random() * 250;
      console.warn(`  retrying after ${Math.round(backoff)} ms (${String(error)})`);
      await sleep(backoff);
    }
  }
  throw lastError;
}

export const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Poll until `read` reports a terminal state.
 * The first poll is delayed because these jobs are never ready immediately.
 */
export async function poll<T>(
  read: () => Promise<T>,
  isDone: (value: T) => boolean,
  isFailed: (value: T) => boolean,
  { initialDelayMs = 12_000, intervalMs = 4_000, timeoutMs = 900_000, label = 'job' } = {}
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  await sleep(initialDelayMs);
  let ticks = 0;
  while (Date.now() < deadline) {
    const value = await read();
    if (isDone(value)) return value;
    if (isFailed(value)) throw new Error(`${label} failed: ${JSON.stringify(value).slice(0, 300)}`);
    if (ticks % 5 === 0) process.stdout.write(`  waiting for ${label}… ${Math.round((Date.now() - (deadline - timeoutMs)) / 1000)}s\n`);
    ticks += 1;
    await sleep(intervalMs);
  }
  throw new Error(`${label} timed out after ${Math.round(timeoutMs / 1000)}s`);
}

export async function download(url: string, file: string): Promise<number> {
  const { writeFile, mkdir } = await import('node:fs/promises');
  const { dirname } = await import('node:path');
  const headers = url.startsWith(BASE_URL) ? { Authorization: `Bearer ${apiKey()}` } : undefined;
  const response = await fetch(url, { headers, redirect: 'follow' });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  const bytes = Buffer.from(await response.arrayBuffer());
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, bytes);
  return bytes.length;
}
