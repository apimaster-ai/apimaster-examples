/**
 * Text-to-image and image-to-image.
 *
 *   npm run image -- "a corgi astronaut on the moon" --size 16:9 --resolution 2k
 *   npm run image -- "make the background a desert sunset" --ref https://example.com/a.png
 *   npm run image -- "a detailed matte painting" --resolution 4k --async
 */
import { ApiError, api, download, poll } from './client.js';

interface SyncImageResponse {
  created: number;
  data: Array<{ url?: string; b64_json?: string }>;
}

interface AsyncSubmitResponse {
  code: number;
  data: Array<{ status: string; task_id: string }>;
}

interface TaskResponse {
  data?: {
    status?: string;
    result?: { images?: Array<{ url?: string | string[] }> };
  };
}

// A 4k render can legitimately take ten minutes. A shorter timeout aborts healthy jobs
// that you have already been charged for.
const SYNC_TIMEOUT: Record<string, number> = { '1k': 200_000, '2k': 320_000, '4k': 620_000 };

const argv = process.argv.slice(2);

function arg(name: string): string | undefined {
  const index = argv.indexOf(`--${name}`);
  return index === -1 ? undefined : argv[index + 1];
}

function args(name: string): string[] {
  return argv.filter((_, i) => argv[i - 1] === `--${name}`);
}

function flag(name: string): boolean {
  return argv.includes(`--${name}`);
}

async function main() {
  const prompt = argv
    .filter((value, i) => !value.startsWith('--') && !argv[i - 1]?.startsWith('--'))
    .join(' ');
  if (!prompt) {
    console.error(
      'usage: npm run image -- "<prompt>" [--size 16:9] [--resolution 2k] [--ref <url>] [--async]'
    );
    process.exit(1);
  }

  const model = arg('model') ?? 'gpt-image-2';
  const resolution = arg('resolution') ?? '1k';
  const size = arg('size');
  const references = args('ref');

  const body: Record<string, unknown> = { model, prompt, resolution };
  if (size) body.size = size;
  if (references.length) body.image_urls = references;

  console.log(`generating with ${model} (${resolution}${size ? `, ${size}` : ''})`);
  const started = Date.now();
  let urls: string[];

  if (flag('async')) {
    const submit = await api<AsyncSubmitResponse>('/images/generations/async', {
      method: 'POST',
      body,
    });
    const taskId = submit.data?.[0]?.task_id;
    if (!taskId) throw new Error(`no task_id in response: ${JSON.stringify(submit)}`);
    console.log(`  task ${taskId}`);

    const done = await poll<TaskResponse>(
      () => api<TaskResponse>(`/tasks/${taskId}?model=${encodeURIComponent(model)}`, { timeoutMs: 30_000 }),
      (value) => value.data?.status === 'completed',
      (value) => ['failed', 'error', 'cancelled'].includes(value.data?.status ?? ''),
      { label: 'image' }
    );
    urls = (done.data?.result?.images ?? []).flatMap((image) =>
      Array.isArray(image.url) ? image.url : image.url ? [image.url] : []
    );
  } else {
    try {
      const response = await api<SyncImageResponse>('/images/generations', {
        method: 'POST',
        body,
        timeoutMs: SYNC_TIMEOUT[resolution] ?? 200_000,
        retries: 0,
      });
      urls = response.data.map((item) => item.url).filter((url): url is string => Boolean(url));
    } catch (error) {
      if (error instanceof ApiError && error.status === 408) {
        console.error('Sync generation timed out. Re-run the same command with --async.');
      }
      throw error;
    }
  }

  if (!urls.length) throw new Error('the endpoint returned no image URLs');

  for (const [index, url] of urls.entries()) {
    const file = `out/image-${Date.now()}-${index + 1}.png`;
    const bytes = await download(url, file);
    console.log(`  saved ${file} (${Math.round(bytes / 1024)} KB)`);
  }
  console.log(`done in ${Math.round((Date.now() - started) / 1000)}s`);
}

main().catch((error) => {
  console.error(`\n${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
