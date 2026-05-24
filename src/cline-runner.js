/**
 * ClineRunner — Runs Cline tasks with streaming callbacks.
 *
 * Wraps the Cline CLI (`cline`) to execute tasks in a specific directory
 * with streaming progress callbacks. Supports plan mode (-p flag), timeouts,
 * and progress events.
 *
 * Exports a singleton instance.
 */

const { spawn } = require('child_process');
const path = require('path');

const LOG_PREFIX = '[ClineRunner]';
const DEFAULT_TIMEOUT = 300_000; // 5 minutes

/**
 * Default progress interval (ms) — emit a progress tick every 15s
 * if no other events are firing.
 */
const PROGRESS_INTERVAL = 15_000;

class ClineRunner {
  /**
   * Run a Cline task with streaming callbacks.
   *
   * @param {string} prompt - The task prompt to send to Cline
   * @param {object} options
   * @param {string} [options.workdir] - Directory to run in (defaults to cwd)
   * @param {boolean} [options.planMode] - If true, use plan mode (-p flag)
   * @param {number} [options.timeout] - Max time in ms (default: 300000)
   * @param {object} [callbacks]
   * @param {Function} [callbacks.onStart] - Called when Cline starts
   * @param {Function} [callbacks.onChunk] - Called with each output chunk { text }
   * @param {Function} [callbacks.onProgress] - Called periodically with { elapsed, text }
   * @param {Function} [callbacks.onComplete] - Called on success { output, exitCode }
   * @param {Function} [callbacks.onError] - Called on failure { error, exitCode, output }
   *
   * @returns {Promise<{ success: boolean, output: string, exitCode: number }>}
   */
  async runTaskWithStreaming(prompt, options = {}, callbacks = {}) {
    const {
      workdir = process.cwd(),
      planMode = false,
      timeout = DEFAULT_TIMEOUT,
    } = options;

    const {
      onStart,
      onChunk,
      onProgress,
      onComplete,
      onError,
    } = callbacks;

    const args = planMode ? ['-p', prompt] : [prompt];
    let fullOutput = '';
    const startTime = Date.now();
    let progressTimer = null;

    // Periodic progress reporting
    if (onProgress) {
      progressTimer = setInterval(() => {
        const elapsed = Date.now() - startTime;
        onProgress({
          elapsed,
          text: fullOutput.slice(-500), // Last 500 chars
        });
      }, PROGRESS_INTERVAL);
    }

    return new Promise((resolve) => {
      console.log(
        `${LOG_PREFIX} Starting Cline task: planMode=${planMode}, workdir=${workdir}, timeout=${timeout}ms`
      );

      let child;
      try {
        child = spawn('cline', args, {
          cwd: workdir,
          env: { ...process.env },
          stdio: ['pipe', 'pipe', 'pipe'],
        });
      } catch (err) {
        const errMsg = `Failed to spawn Cline process: ${err.message}`;
        console.error(`${LOG_PREFIX} ${errMsg}`);
        if (onError) onError({ error: errMsg, exitCode: -1, output: '' });
        if (progressTimer) clearInterval(progressTimer);
        resolve({ success: false, output: '', exitCode: -1, error: errMsg });
        return;
      }

      if (onStart) onStart({ workdir, planMode });

      // Timeout handling
      let timedOut = false;
      const timeoutTimer = setTimeout(() => {
        timedOut = true;
        console.error(`${LOG_PREFIX} Task timed out after ${timeout}ms`);
        child.kill('SIGTERM');

        // Grace period then force kill
        setTimeout(() => {
          try {
            child.kill('SIGKILL');
          } catch {
            // Process may already be gone
          }
        }, 5000);
      }, timeout);

      child.stdout.on('data', (data) => {
        const text = data.toString();
        fullOutput += text;
        if (onChunk) onChunk({ text });
      });

      child.stderr.on('data', (data) => {
        const text = data.toString();
        fullOutput += text;
        if (onChunk) onChunk({ text });
      });

      child.on('error', (err) => {
        if (timedOut) return; // Already handled
        clearTimeout(timeoutTimer);
        if (progressTimer) clearInterval(progressTimer);

        const errMsg = `Cline process error: ${err.message}`;
        console.error(`${LOG_PREFIX} ${errMsg}`);
        if (onError) onError({ error: errMsg, exitCode: -1, output: fullOutput });
        resolve({ success: false, output: fullOutput, exitCode: -1, error: errMsg });
      });

      child.on('close', (code) => {
        clearTimeout(timeoutTimer);
        if (progressTimer) clearInterval(progressTimer);

        const elapsed = Date.now() - startTime;
        const success = code === 0 && !timedOut;

        console.log(
          `${LOG_PREFIX} Cline task finished: code=${code}, timedOut=${timedOut}, elapsed=${elapsed}ms`
        );

        if (success) {
          if (onComplete) onComplete({ output: fullOutput, exitCode: code });
          resolve({ success: true, output: fullOutput, exitCode: code });
        } else {
          const errMsg = timedOut
            ? `Task timed out after ${timeout}ms`
            : `Cline exited with code ${code}`;
          if (onError) onError({ error: errMsg, exitCode: code, output: fullOutput });
          resolve({ success: false, output: fullOutput, exitCode: code, error: errMsg });
        }
      });
    });
  }

  /**
   * Run a task in plan mode (shortcut).
   * @param {string} prompt
   * @param {object} options
   * @param {object} callbacks
   * @returns {Promise<{ success: boolean, output: string, exitCode: number }>}
   */
  async runPlanMode(prompt, options = {}, callbacks = {}) {
    return this.runTaskWithStreaming(prompt, { ...options, planMode: true }, callbacks);
  }
}

module.exports = new ClineRunner();
