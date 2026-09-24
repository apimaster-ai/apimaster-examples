/**
 * Multi-turn chat with the OpenAI SDK pointed at a gateway.
 *
 *   npm run chat -- "who won the 2018 world cup?"
 *
 * The important detail: the full message history goes out on every request. Server-side
 * conversation continuation (previous_response_id / store) is not reliable on this
 * gateway, and code that depends on it silently loses context in production.
 */
import OpenAI from 'openai';
import { BASE_URL, apiKey } from './client.js';

const MODEL = process.env.MODEL ?? 'gpt-5.5';

const client = new OpenAI({ baseURL: BASE_URL, apiKey: apiKey() });

type Turn = { role: 'user' | 'assistant' | 'system'; content: string };

async function ask(history: Turn[], question: string): Promise<string> {
  history.push({ role: 'user', content: question });

  const stream = await client.chat.completions.create({
    model: MODEL,
    messages: history,
    stream: true,
    temperature: 0.3,
  });

  let answer = '';
  let firstTokenAt: number | null = null;
  const started = Date.now();
  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta?.content;
    if (!delta) continue;
    firstTokenAt ??= Date.now();
    answer += delta;
    process.stdout.write(delta);
  }
  process.stdout.write('\n');
  console.log(
    `  [${MODEL}] first token ${firstTokenAt ? firstTokenAt - started : '?'} ms · total ${Date.now() - started} ms`
  );

  history.push({ role: 'assistant', content: answer });
  return answer;
}

async function main() {
  const question = process.argv.slice(2).join(' ') || 'Name three things that make a CLI feel fast.';
  const history: Turn[] = [{ role: 'system', content: 'You are concise. Answer in at most three sentences.' }];

  await ask(history, question);
  // The follow-up only works because the whole history is resent above.
  await ask(history, 'Now say the same thing in one sentence.');
}

main().catch((error) => {
  console.error(`\n${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
