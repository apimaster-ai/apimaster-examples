/**
 * Text-to-video and image-to-video, with polling and download.
 *
 *   npm run video -- "a waterfall forming a rainbow, cinematic" --duration 4
 *   npm run video -- "slow push-in, hair in the breeze" --ref https://example.com/face.jpg --aspect 9:16
 */
import { BASE_URL, api, download, poll } from './client.js';

interface SubmitResponse {
  code?: number;
  data?: Array<{ status: string; task_id: string }>;
  id?: string;
}

interface StatusResponse {
  id: string;
  status: 'queued' | 'in_progress' | 'completed' | 'failed' | string;
  url?: string;
}

function arg(name: string): string | undefined {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? undefined : process.argv[index + 1];
}

async function main() {
  const argv = process.argv.slice(2);
  const prompt = argv
    .filter((value, i) => !value.startsWith('--') && !argv[i - 1]?.startsWith('--'))
    .join(' ');
  if (!prompt) {
    console.error('usage: npm run video -- "<prompt>" [--duration 4] [--aspect 16:9] [--ref <url>]');
    process.exit(1);
  }

  const model = arg('model') ?? 'seedance-2.5';
  const reference = arg('ref');
  const body: Record<string, unknown> = {
    model,
    prompt,
    duration: Number(arg('duration') ?? 4),
    resolution: arg('resolution') ?? '720p',
    // Always explicit: a portrait reference with no aspect_ratio comes back 16:9.
    aspect_ratio: arg('aspect') ?? '16:9',
  };
  if (reference) body.image_urls = [reference];

  console.log(
    `submitting ${model}: ${String(body.duration)}s ${String(body.resolution)} ${String(body.aspect_ratio)}`
  );
  const started = Date.now();

  const submit = await api<SubmitResponse>('/videos/generations', { method: 'POST', body });
  const taskId = submit.data?.[0]?.task_id ?? submit.id;
  if (!taskId) throw new Error(`no task id in response: ${JSON.stringify(submit)}`);
  console.log(`  task ${taskId} — video is slow, often 10-15 minutes`);

  const done = await poll<StatusResponse>(
    () => api<StatusResponse>(`/videos/${taskId}`, { timeoutMs: 30_000 }),
    (value) => value.status === 'completed',
    (value) => ['failed', 'error', 'cancelled'].includes(value.status),
    { initialDelayMs: 15_000, timeoutMs: 1_800_000, label: 'video' } // seedance-2.5: ~15 min for 4 s
  );

  const contentUrl = done.url ?? `${BASE_URL}/videos/${taskId}/content`;
  const file = `out/${model}-${taskId.slice(-8)}.mp4`;
  const bytes = await download(contentUrl, file);
  console.log(
    `  saved ${file} (${(bytes / 1e6).toFixed(1)} MB) in ${Math.round((Date.now() - started) / 1000)}s`
  );
}

main().catch((error) => {
  console.error(`\n${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
