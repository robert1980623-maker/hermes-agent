/**
 * HarnessOrchestrator — Core orchestrator for the full harness workflow.
 *
 * Manages the complete lifecycle:
 *   Plan → Execution Plan → Parallel Worktree Development → Code Review + QA → Merge
 *
 * Uses PlanParser, WorktreeManager, ClineRunner, and HarnessMode.
 * Reports progress via a callback system.
 *
 * Exports a singleton instance.
 */

const planParser = require('./plan-parser');
const worktreeManager = require('./worktree-manager');
const clineRunner = require('./cline-runner');
const harnessMode = require('./harness-mode');

const LOG_PREFIX = '[HarnessOrchestrator]';
const DEFAULT_MAX_PARALLEL = 3;
const DEFAULT_TASK_TIMEOUT = 300_000; // 5 minutes

/**
 * Helper: run an async operation with a timeout.
 */
function _withTimeout(promise, ms, context) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`Timeout after ${ms}ms: ${context}`)),
      ms
    );
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

class HarnessOrchestrator {
  constructor() {
    this.maxParallel = DEFAULT_MAX_PARALLEL;
    this.taskTimeout = DEFAULT_TASK_TIMEOUT;
    // channelId -> { phase, tasks, worktrees, executionPlan, plan }
    this.sessionState = new Map();
  }

  /**
   * Execute the full harness workflow.
   *
   * @param {string} prompt - User's original task/request
   * @param {object} [callbacks]
   * @param {Function} [callbacks.onPhase] - ({ phase, description, total }) phase change
   * @param {Function} [callbacks.onTaskStart] - ({ taskId, phase, description }) task starting
   * @param {Function} [callbacks.onTaskComplete] - ({ taskId, phase, success, duration }) task done
   * @param {Function} [callbacks.onReview] - ({ taskId, passed, notes }) code review result
   * @param {Function} [callbacks.onQA] - ({ taskId, passed, output }) QA check result
   * @param {Function} [callbacks.onMerge] - ({ taskId, success }) merge result
   * @param {Function} [callbacks.onProgress] - ({ report }) periodic progress report
   * @param {Function} [callbacks.onError] - ({ error, phase, taskId }) error event
   * @param {object} [options]
   * @param {string} [options.workdir] - Repository directory
   * @param {number} [options.maxParallel] - Max concurrent worktrees (default: 3)
   * @param {number} [options.taskTimeout] - Per-task timeout in ms (default: 300000)
   * @param {string} [options.channelId] - Slack channel for session tracking
   *
   * @returns {Promise<{ success: boolean, plan, executionPlan, results }>}
   */
  async executeWorkflow(prompt, callbacks = {}, options = {}) {
    const {
      workdir = process.cwd(),
      maxParallel = DEFAULT_MAX_PARALLEL,
      taskTimeout = DEFAULT_TASK_TIMEOUT,
      channelId = 'default',
    } = options;

    this.maxParallel = maxParallel;
    this.taskTimeout = taskTimeout;

    // Initialize session state
    const state = {
      phase: 'plan',
      tasks: new Map(),
      worktrees: new Set(),
      executionPlan: null,
      plan: null,
      results: {},
      workdir,
    };
    this.sessionState.set(channelId, state);

    // Configure worktree manager workdir
    worktreeManager.cwd = workdir;
    worktreeManager.harnessDir = `${workdir}/.harness/worktrees`;

    try {
      // Phase 1: Plan
      this._log('Starting Phase 1: PLAN');
      callbacks.onPhase?.({ phase: 'plan', description: 'Analyzing request and generating plan', total: 5 });
      const plan = await this._runPlanPhase(prompt, workdir, callbacks);
      state.plan = plan;

      // Phase 2: Build Execution Plan
      this._log('Starting Phase 2: BUILD EXECUTION PLAN');
      callbacks.onPhase?.({ phase: 'execution-plan', description: 'Building phased execution schedule', total: 5 });
      const executionPlan = planParser.buildExecutionPlan(plan);
      state.executionPlan = executionPlan;
      this._log(`Execution plan: ${executionPlan.phases.length} phases, ${plan.tasks.length} tasks total`);

      // Initialize task state
      for (const phase of executionPlan.phases) {
        for (const task of phase.tasks) {
          state.tasks.set(task.id, {
            ...task,
            status: 'pending',
            phase: phase.phase,
          });
        }
      }

      // Phase 3: Parallel Development
      for (const phase of executionPlan.phases) {
        await this._runPhase(phase, plan, state, callbacks);
      }

      // Phase 4: Code Review + QA
      this._log('Starting Phase 4: CODE REVIEW + QA');
      callbacks.onPhase?.({ phase: 'review-qa', description: 'Running code review and QA checks', total: 5 });

      const completedTasks = Array.from(state.tasks.values()).filter(
        (t) => t.status === 'completed'
      );

      for (const task of completedTasks) {
        await this._runCodeReview(task.id, state, callbacks);
        await this._runQACheck(task.id, state, callbacks);
      }

      // Check if all tasks passed review + QA
      const allPassed = completedTasks.every(
        (t) => state.results[t.id]?.reviewPassed && state.results[t.id]?.qaPassed
      );

      if (!allPassed) {
        const failed = completedTasks.filter(
          (t) => !state.results[t.id]?.reviewPassed || !state.results[t.id]?.qaPassed
        );
        throw new Error(
          `${failed.length} task(s) failed review/QA: ${failed.map((t) => t.id).join(', ')}`
        );
      }

      // Phase 5: Merge
      this._log('Starting Phase 5: MERGE');
      callbacks.onPhase?.({ phase: 'merge', description: 'Merging worktrees in dependency order', total: 5 });
      await this._runMergePhase(executionPlan, state, callbacks);

      // Final progress report
      this._log('Workflow completed successfully');
      callbacks.onPhase?.({ phase: 'complete', description: 'All tasks merged successfully', total: 5 });

      return {
        success: true,
        plan,
        executionPlan,
        results: state.results,
      };
    } catch (err) {
      this._log(`Workflow failed: ${err.message}`);
      callbacks.onError?.({ error: err.message, phase: state.phase });

      // Cleanup on failure
      this._log('Cleaning up worktrees after failure');
      try {
        await worktreeManager.cleanupAll();
      } catch (cleanupErr) {
        this._log(`Cleanup warning: ${cleanupErr.message}`);
      }

      callbacks.onPhase?.({ phase: 'failed', description: `Workflow failed: ${err.message}`, total: 5 });

      return {
        success: false,
        error: err.message,
        plan: state.plan,
        executionPlan: state.executionPlan,
        results: state.results,
      };
    } finally {
      this.sessionState.delete(channelId);
    }
  }

  /**
   * Phase 1: Use Cline in plan mode to analyze the prompt and generate a plan.
   */
  async _runPlanPhase(prompt, workdir, callbacks) {
    const planPrompt = harnessMode.injectWorkflowPrinciples(prompt);

    let planOutput = '';

    const result = await _withTimeout(
      clineRunner.runPlanMode(planPrompt, { workdir }, {
        onStart: () => this._log('Cline plan mode started'),
        onChunk: ({ text }) => {
          planOutput += text;
        },
        onProgress: ({ elapsed }) => {
          this._log(`Plan generation in progress: ${Math.round(elapsed / 1000)}s`);
        },
      }),
      this.taskTimeout,
      'Plan phase'
    );

    if (!result.success) {
      throw new Error(`Plan phase failed: ${result.error || 'Unknown error'}`);
    }

    this._log(`Plan output received (${planOutput.length} chars)`);

    // Parse and validate
    const plan = planParser.parsePlanOutput(planOutput);
    const validation = planParser.validatePlan(plan);

    if (!validation.valid) {
      const err = new Error(`Plan validation failed: ${validation.errors.join('; ')}`);
      this._log(err.message);
      throw err;
    }

    this._log(`Plan parsed: ${plan.tasks.length} tasks`);
    this._log(planParser.generateChecklist(plan));

    // Send summary via callback
    callbacks.onProgress?.({
      report: {
        type: 'plan-summary',
        design: plan.design,
        taskCount: plan.tasks.length,
        checklist: planParser.generateChecklist(plan),
      },
    });

    return plan;
  }

  /**
   * Phase 3: Run all tasks for a given execution phase.
   * Tasks within a phase are independent and run in parallel (up to maxParallel).
   */
  async _runPhase(phase, plan, state, callbacks) {
    const phaseNum = phase.phase;
    const tasks = phase.tasks;

    this._log(`Phase ${phaseNum}: ${tasks.length} task(s) to run`);
    callbacks.onPhase?.({
      phase: `development-${phaseNum}`,
      description: `Phase ${phaseNum}: Developing ${tasks.length} task(s) in parallel`,
      total: 5,
    });

    // Run tasks in batches of maxParallel
    const batches = [];
    for (let i = 0; i < tasks.length; i += this.maxParallel) {
      batches.push(tasks.slice(i, i + this.maxParallel));
    }

    for (const batch of batches) {
      const batchPromises = batch.map((task) =>
        this._runTaskInWorktree(task, plan, state, callbacks)
      );
      const results = await Promise.allSettled(batchPromises);

      // Check for failures
      for (let i = 0; i < results.length; i++) {
        const r = results[i];
        const task = batch[i];
        if (r.status === 'rejected') {
          this._log(`Task ${task.id} failed: ${r.reason.message}`);
          // Mark task as failed but don't stop — let review phase catch it
          state.tasks.set(task.id, {
            ...task,
            status: 'failed',
            phase: phaseNum,
            error: r.reason.message,
          });
        }
      }
    }

    // Report phase completion
    const completedCount = Array.from(state.tasks.values()).filter(
      (t) => t.phase === phaseNum && t.status === 'completed'
    ).length;
    this._log(`Phase ${phaseNum} complete: ${completedCount}/${tasks.length} tasks succeeded`);
  }

  /**
   * Run a single task: create worktree → run Cline → commit.
   */
  async _runTaskInWorktree(task, plan, state, callbacks) {
    const startTime = Date.now();
    this._log(`Task ${task.id}: starting — "${task.description.slice(0, 80)}..."`);
    callbacks.onTaskStart?.({
      taskId: task.id,
      phase: task.phase,
      description: task.description,
    });

    // Create worktree
    const branchName = `harness/${task.id}`;
    const wtResult = await worktreeManager.createWorktree(task.id, branchName);
    if (!wtResult.success) {
      throw new Error(`Failed to create worktree for ${task.id}: ${wtResult.error}`);
    }
    state.worktrees.add(task.id);
    this._log(`Worktree created for ${task.id} at ${wtResult.path}`);

    // Generate task prompt
    const taskPrompt = planParser.getTaskPrompt(task, plan);

    // Run Cline in the worktree
    let taskOutput = '';
    const clineResult = await _withTimeout(
      clineRunner.runTaskWithStreaming(taskPrompt, {
        workdir: wtResult.path,
        planMode: false,
        timeout: this.taskTimeout,
      }, {
        onStart: () => this._log(`Cline started for ${task.id}`),
        onChunk: ({ text }) => {
          taskOutput += text;
        },
        onProgress: ({ elapsed }) => {
          this._log(`${task.id} in progress: ${Math.round(elapsed / 1000)}s elapsed`);
        },
      }),
      this.taskTimeout,
      `Task ${task.id} execution`
    );

    if (!clineResult.success) {
      throw new Error(`Cline task failed for ${task.id}: ${clineResult.error}`);
    }

    // Commit changes
    const commitMsg = `[harness] ${task.id}: ${task.description}`;
    const commitResult = await worktreeManager.commitWorktree(task.id, commitMsg);
    if (!commitResult.success) {
      throw new Error(`Failed to commit worktree for ${task.id}: ${commitResult.error}`);
    }

    const duration = Date.now() - startTime;
    this._log(`Task ${task.id} completed in ${Math.round(duration / 1000)}s, commit: ${commitResult.commitHash}`);

    state.tasks.set(task.id, {
      ...task,
      status: 'completed',
      commitHash: commitResult.commitHash,
      duration,
    });

    state.results[task.id] = {
      ...state.results[task.id],
      commitHash: commitResult.commitHash,
      duration,
    };

    callbacks.onTaskComplete?.({
      taskId: task.id,
      phase: task.phase,
      success: true,
      duration,
      commitHash: commitResult.commitHash,
    });

    // Send progress report
    callbacks.onProgress?.({
      report: this._getProgressReport(state),
    });
  }

  /**
   * Phase 4a: Run code review on a completed worktree.
   * Uses Cline in plan mode to review the changes.
   */
  async _runCodeReview(taskId, state, callbacks) {
    const task = state.tasks.get(taskId);
    if (!task || task.status !== 'completed') {
      this._log(`${taskId}: skipping review — status is ${task?.status || 'unknown'}`);
      return;
    }

    this._log(`${taskId}: starting code review`);

    const reviewPrompt = planParser.getCodeReviewPrompt();
    const wtPath = `${worktreeManager.harnessDir}/${taskId}`;

    let reviewOutput = '';
    const reviewResult = await _withTimeout(
      clineRunner.runPlanMode(reviewPrompt, { workdir: wtPath }, {
        onChunk: ({ text }) => {
          reviewOutput += text;
        },
      }),
      this.taskTimeout,
      `Code review for ${taskId}`
    );

    const passed = reviewResult.success;
    state.results[taskId] = {
      ...state.results[taskId],
      reviewPassed: passed,
      reviewOutput: reviewOutput.slice(-2000), // Keep last 2K chars
    };

    this._log(`${taskId}: code review ${passed ? 'PASSED' : 'FAILED'}`);

    callbacks.onReview?.({
      taskId,
      passed,
      notes: passed ? 'No issues found' : reviewOutput.slice(-500),
    });
  }

  /**
   * Phase 4b: Run QA checks on a completed worktree.
   * Attempts to run npm test and npm lint if available.
   */
  async _runQACheck(taskId, state, callbacks) {
    const task = state.tasks.get(taskId);
    if (!task || task.status !== 'completed') {
      this._log(`${taskId}: skipping QA — status is ${task?.status || 'unknown'}`);
      return;
    }

    this._log(`${taskId}: starting QA check`);

    const wtPath = `${worktreeManager.harnessDir}/${taskId}`;
    let allPassed = true;
    let qaOutput = '';

    // Try npm test
    try {
      this._log(`${taskId}: running npm test`);
      const { spawn } = require('child_process');
      const testResult = await new Promise((resolve) => {
        const child = spawn('npm', ['test'], { cwd: wtPath, stdio: ['pipe', 'pipe', 'pipe'] });
        let output = '';
        child.stdout.on('data', (d) => (output += d.toString()));
        child.stderr.on('data', (d) => (output += d.toString()));
        child.on('close', (code) => resolve({ code, output }));
        child.on('error', () => resolve({ code: -1, output: 'npm test not available' }));
      });

      qaOutput += `TEST: ${testResult.code === 0 ? 'PASS' : 'FAIL'}\n${testResult.output.slice(-1000)}\n\n`;
      if (testResult.code !== 0) allPassed = false;
    } catch (err) {
      qaOutput += `TEST: SKIP (${err.message})\n\n`;
      this._log(`${taskId}: npm test skipped: ${err.message}`);
    }

    // Try npm run lint
    try {
      this._log(`${taskId}: running npm run lint`);
      const { spawn } = require('child_process');
      const lintResult = await new Promise((resolve) => {
        const child = spawn('npm', ['run', 'lint'], { cwd: wtPath, stdio: ['pipe', 'pipe', 'pipe'] });
        let output = '';
        child.stdout.on('data', (d) => (output += d.toString()));
        child.stderr.on('data', (d) => (output += d.toString()));
        child.on('close', (code) => resolve({ code, output }));
        child.on('error', () => resolve({ code: -1, output: 'lint not available' }));
      });

      qaOutput += `LINT: ${lintResult.code === 0 ? 'PASS' : 'FAIL'}\n${lintResult.output.slice(-1000)}`;
      if (lintResult.code !== 0) allPassed = false;
    } catch (err) {
      qaOutput += `LINT: SKIP (${err.message})\n`;
      this._log(`${taskId}: npm lint skipped: ${err.message}`);
    }

    state.results[taskId] = {
      ...state.results[taskId],
      qaPassed: allPassed,
      qaOutput,
    };

    this._log(`${taskId}: QA check ${allPassed ? 'PASSED' : 'FAILED'}`);

    callbacks.onQA?.({
      taskId,
      passed: allPassed,
      output: qaOutput.slice(-500),
    });
  }

  /**
   * Phase 5: Merge all worktrees in dependency order.
   */
  async _runMergePhase(executionPlan, state, callbacks) {
    // Merge in phase order (earlier phases first), which respects dependencies
    for (const phase of executionPlan.phases) {
      for (const task of phase.tasks) {
        const taskState = state.tasks.get(task.id);
        if (taskState?.status !== 'completed') {
          this._log(`Skipping merge for ${task.id}: status is ${taskState?.status || 'unknown'}`);
          continue;
        }

        this._log(`Merging ${task.id} into main`);

        const mergeResult = await _withTimeout(
          worktreeManager.mergeWorktree(task.id, 'main'),
          60_000, // 60s timeout for merge
          `Merge of ${task.id}`
        );

        const success = mergeResult.success;
        state.results[task.id] = {
          ...state.results[task.id],
          merged: success,
          conflicts: mergeResult.conflicts,
        };

        if (success) {
          this._log(`${task.id}: merge successful`);
        } else {
          this._log(`${task.id}: merge failed — ${mergeResult.error || (mergeResult.conflicts ? 'conflicts' : 'unknown')}`);
          throw new Error(
            `Merge failed for ${task.id}: ${mergeResult.error || (mergeResult.conflicts ? 'merge conflicts' : 'unknown error')}`
          );
        }

        callbacks.onMerge?.({ taskId: task.id, success, conflicts: mergeResult.conflicts });
      }
    }

    // Final integration check
    this._log('Running final integration check');

    // Clean up worktrees
    this._log('Cleaning up worktrees');
    const cleanup = await worktreeManager.cleanupAll();
    state.worktrees.clear();

    if (!cleanup.success) {
      this._log(`Cleanup warnings: ${cleanup.errors.join(', ')}`);
    }

    this._log(`Cleanup complete: ${cleanup.removed} worktrees removed`);
  }

  /**
   * Generate a progress report from the current session state.
   */
  _getProgressReport(state) {
    const tasks = Array.from(state.tasks.values());
    const total = tasks.length;
    const completed = tasks.filter((t) => t.status === 'completed').length;
    const failed = tasks.filter((t) => t.status === 'failed').length;
    const pending = tasks.filter((t) => t.status === 'pending').length;
    const inReview = tasks.filter(
      (t) =>
        t.status === 'completed' &&
        (!state.results[t.id]?.reviewPassed || !state.results[t.id]?.qaPassed)
    ).length;

    return {
      phase: state.phase,
      total,
      completed,
      failed,
      pending,
      inReview,
      worktrees: state.worktrees.size,
      taskDetails: tasks.map((t) => ({
        id: t.id,
        status: t.status,
        phase: t.phase,
      })),
    };
  }

  /**
   * Structured logging helper.
   */
  _log(msg) {
    console.log(`${LOG_PREFIX} ${msg}`);
  }

  /**
   * Get the current session state for a channel (for debugging/status queries).
   */
  getSessionState(channelId) {
    return this.sessionState.get(channelId) || null;
  }
}

module.exports = new HarnessOrchestrator();
