// Local JSON protocol: Python owns model calls; the vendored engine owns video processing.
import { writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { probeVideo } from './vendor/src/probe.js';
import { scanShots } from './vendor/src/scan.js';
import { planWindows } from './vendor/src/plan.js';
import { runStoryboard, formatManifest, formatProbe, formatTimeline, DETAIL_CHARS } from './vendor/src/pipeline.js';
import { validateToolArgs, validateZoomArgs } from './vendor/src/tool-spec.js';

async function render(options, output, indexOptions) {
  const result = await runStoryboard(options);
  const images = [];
  for (const sheet of result.sheets) {
    const path = join(output, `sheet-${sheet.sheet}.png`);
    await writeFile(path, sheet.png);
    images.push(path);
  }
  const text = formatManifest(result, indexOptions);
  const manifest = {
    info: result.info, window: result.window, plan: result.plan,
    cuts: result.cuts, summary: result.summary, cached: result.cached,
    transcript: result.transcript, audio: result.audio,
    cells: result.cells ?? result.sheets.flatMap((s) => s.cells), images, text,
  };
  const manifestPath = join(output, 'manifest.json');
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2));
  return { ...manifest, manifest_path: manifestPath };
}

export async function execute(request) {
  const { operation, options = {}, output } = request;
  if (!options.input) throw new Error('input is required');
  const info = { ...await probeVideo(options.input), path: options.input };
  if (!(info.duration > 0)) throw new Error('video duration must be positive');
  if (operation === 'probe') return { info, text: formatProbe(info), images: [] };
  if (!output) throw new Error('output directory is required');
  await mkdir(output, { recursive: true });
  // Reject out-of-range windows instead of upstream's silent end clamping.
  const start = options.from ?? 0;
  const end = options.to ?? info.duration;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || start >= info.duration || end <= start) {
    throw new RangeError('window must satisfy 0 <= from < duration and to > from');
  }
  const validationArgs = { ...options };
  for (const name of ['cells', 'sheets']) {
    if (validationArgs[name] === 0) delete validationArgs[name];
  }
  const problems = operation === 'zoom' ? validateZoomArgs(validationArgs) : validateToolArgs(validationArgs);
  if (problems.length) throw new RangeError(problems.join('; '));
  const indexOptions = {
    cellRange: options.cellRange ?? null,
    maxCellChars: DETAIL_CHARS[options.detail ?? 'med'], maxChars: 24000,
  };
  if (operation === 'batch') {
    const step = request.step;
    if (!Number.isFinite(step) || step < 10) throw new RangeError('batch step must be >= 10 seconds');
    const scan = request.snap === false ? null : await scanShots({ input: options.input, fps: info.fps, threshold: 'auto' });
    const plan = planWindows(info.duration, step, { boundaries: scan?.cuts.map((c) => c.t) ?? [] });
    const windows = [];
    const rows = [];
    for (const window of plan.windows) {
      const folder = join(output, `window-${window.index}`);
      await mkdir(folder, { recursive: true });
      const result = await render({ ...options, from: window.from, to: window.to, precomputed: scan }, folder, indexOptions);
      windows.push(result);
      rows.push({ index: window.index, from: window.from, to: window.to, cells: result.cells.length,
        cuts: result.cuts.length, chars: result.transcript?.chars ?? 0, image: result.images.join(', ') });
    }
    const text = formatTimeline(rows);
    const timelinePath = join(output, 'timeline.md');
    await writeFile(timelinePath, text);
    return { info, plan, windows, text, timeline_path: timelinePath, images: windows.flatMap((w) => w.images) };
  }
  if (!['storyboard', 'zoom'].includes(operation)) throw new Error(`unknown operation: ${operation}`);
  return render({ ...options, ...(operation === 'zoom' ? { adaptive: false, sheets: 1 } : {}) }, output, indexOptions);
}

try {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const request = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const result = await execute(request);
  process.stdout.write(JSON.stringify({ ok: true, result }));
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(error.message ?? error) }));
  process.exitCode = 1;
}
