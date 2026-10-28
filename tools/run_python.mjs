// Run stdlib project tools with the local venv before trying PATH aliases.
import {existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const venv = join(root, '.venv', ...(process.platform === 'win32'
  ? ['Scripts', 'python.exe'] : ['bin', 'python']));
const candidates = [process.env.DRIVER_MONITOR_PYTHON,
  existsSync(venv) ? venv : null, 'python3', 'python'].filter(Boolean);
const args = process.argv.slice(2);
if (args.length === 0) {
  console.error('Usage: node tools/run_python.mjs SCRIPT [ARGS...]');
  process.exit(2);
}
for (const executable of candidates) {
  const child = spawnSync(executable, args, {cwd: root, stdio: 'inherit', shell: false,
    env: {...process.env, PYTHONUTF8: '1'}});
  if (child.error) continue;
  if (child.signal) {
    console.error(`Python stopped by ${child.signal}`);
    process.exit(1);
  }
  process.exit(child.status ?? 1);
}
console.error('No runnable Python found. Create .venv or set DRIVER_MONITOR_PYTHON.');
process.exit(1);
