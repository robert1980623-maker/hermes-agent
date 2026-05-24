/**
 * WorktreeManager — Git worktree lifecycle management for parallel development.
 *
 * Uses child_process.spawn for all git operations.
 * Exports a singleton instance.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const LOG_PREFIX = '[WorktreeManager]';

/**
 * Run a git command via spawn, return trimmed stdout.
 * Rejects if the process exits non-zero or stderr contains errors.
 */
function _spawn(command, args = [], workdir) {
  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';

    const opts = {};
    if (workdir) {
      opts.cwd = workdir;
    }

    const child = spawn(command, args, opts);

    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('error', (err) => {
      reject(err);
    });

    child.on('close', (code) => {
      if (code !== 0) {
        const err = new Error(
          `Command "${command} ${args.join(' ')}" failed with code ${code}: ${stderr.trim()}`
        );
        err.code = code;
        err.stderr = stderr.trim();
        reject(err);
      } else {
        resolve(stdout.trim());
      }
    });
  });
}

class WorktreeManager {
  constructor(cwd) {
    this.cwd = cwd || process.cwd();
    this.harnessDir = path.join(this.cwd, '.harness', 'worktrees');
  }

  /**
   * Create a worktree for a task.
   * @param {string} taskId - Unique task identifier (used as directory name)
   * @param {string} branchName - Branch name to create
   * @param {string} baseBranch - Base branch to create from (default: 'main')
   * @returns {{ success: boolean, path: string, branch: string }}
   */
  async createWorktree(taskId, branchName, baseBranch = 'main') {
    const worktreePath = path.join(this.harnessDir, taskId);

    try {
      // Ensure parent directory exists
      if (!fs.existsSync(this.harnessDir)) {
        fs.mkdirSync(this.harnessDir, { recursive: true });
        console.log(`${LOG_PREFIX} Created harness directory: ${this.harnessDir}`);
      }

      console.log(`${LOG_PREFIX} Creating worktree: taskId=${taskId}, branch=${branchName}, base=${baseBranch}`);

      await _spawn('git', [
        'worktree', 'add', worktreePath, '-b', branchName, baseBranch
      ], this.cwd);

      console.log(`${LOG_PREFIX} Worktree created at ${worktreePath}`);

      return { success: true, path: worktreePath, branch: branchName };
    } catch (err) {
      console.error(`${LOG_PREFIX} Failed to create worktree: ${err.message}`);
      return { success: false, path: worktreePath, branch: branchName, error: err.message };
    }
  }

  /**
   * Remove a worktree by task ID.
   * @param {string} taskId - Task identifier
   * @returns {{ success: boolean }}
   */
  async removeWorktree(taskId) {
    const worktreePath = path.join(this.harnessDir, taskId);

    try {
      console.log(`${LOG_PREFIX} Removing worktree: ${worktreePath}`);

      await _spawn('git', ['worktree', 'remove', worktreePath], this.cwd);

      console.log(`${LOG_PREFIX} Worktree removed: ${worktreePath}`);
      return { success: true };
    } catch (err) {
      console.error(`${LOG_PREFIX} Failed to remove worktree: ${err.message}`);
      return { success: false, error: err.message };
    }
  }

  /**
   * List all active worktrees.
   * Parses `git worktree list` output.
   * @returns {Array<{ path: string, branch: string, commit: string }>}
   */
  async listWorktrees() {
    try {
      const output = await _spawn('git', ['worktree', 'list'], this.cwd);

      // Format: <path> <commit> <ref> <info>
      // Example: /repo/.harness/worktrees/task-1 a1b2c3d [feature/task-1]
      const lines = output.split('\n').filter((line) => line.trim().length > 0);
      const worktrees = [];

      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 3) {
          const wtPath = parts[0];
          const commit = parts[1];
          // Branch is typically in brackets like [refs/heads/feature/task-1] or [feature/task-1]
          const ref = parts[2] || '';
          let branch = ref.replace(/^\[?refs\/heads\//, '').replace(/\]$/, '');

          // Skip the main worktree (no brackets in ref typically)
          // Include all worktrees in the result
          worktrees.push({ path: wtPath, branch, commit });
        }
      }

      return worktrees;
    } catch (err) {
      console.error(`${LOG_PREFIX} Failed to list worktrees: ${err.message}`);
      return [];
    }
  }

  /**
   * Commit changes in a worktree.
   * @param {string} taskId - Task identifier
   * @param {string} message - Commit message
   * @returns {{ success: boolean, commitHash: string }}
   */
  async commitWorktree(taskId, message) {
    const worktreePath = path.join(this.harnessDir, taskId);

    try {
      console.log(`${LOG_PREFIX} Committing in worktree ${taskId}: "${message}"`);

      // Stage all changes
      await _spawn('git', ['add', '-A'], worktreePath);

      // Commit
      await _spawn('git', ['commit', '-m', message], worktreePath);

      // Get the commit hash
      const commitHash = await _spawn('git', ['rev-parse', 'HEAD'], worktreePath);

      console.log(`${LOG_PREFIX} Committed ${commitHash} in worktree ${taskId}`);
      return { success: true, commitHash };
    } catch (err) {
      console.error(`${LOG_PREFIX} Failed to commit in worktree ${taskId}: ${err.message}`);
      return { success: false, commitHash: null, error: err.message };
    }
  }

  /**
   * Merge a worktree branch into the target branch.
   * Runs the merge in the main repository cwd.
   * @param {string} taskId - Task identifier
   * @param {string} targetBranch - Branch to merge into (default: 'main')
   * @returns {{ success: boolean, conflicts: boolean }}
   */
  async mergeWorktree(taskId, targetBranch = 'main') {
    const worktreePath = path.join(this.harnessDir, taskId);

    try {
      // First ensure we're on the target branch
      console.log(`${LOG_PREFIX} Merging worktree branch ${taskId} into ${targetBranch}`);

      // Check out target branch
      await _spawn('git', ['checkout', targetBranch], this.cwd);

      // Attempt merge — use --no-edit to auto-accept merge commit message
      const mergeResult = await _spawn('git', ['merge', '--no-edit', worktreePath], this.cwd);

      console.log(`${LOG_PREFIX} Merge completed for worktree ${taskId}`);
      return { success: true, conflicts: false };
    } catch (err) {
      // Check if this was a merge conflict
      const stderr = err.stderr || '';
      const hasConflicts =
        stderr.includes('CONFLICT') ||
        stderr.includes('merge conflict') ||
        err.code === 128;

      if (hasConflicts) {
        console.warn(`${LOG_PREFIX} Merge conflict for worktree ${taskId}: ${stderr}`);
        return { success: false, conflicts: true, error: stderr };
      }

      console.error(`${LOG_PREFIX} Failed to merge worktree ${taskId}: ${err.message}`);
      return { success: false, conflicts: false, error: err.message };
    }
  }

  /**
   * Remove all harness worktrees.
   * Lists worktrees under .harness/worktrees and removes them one by one.
   * @returns {{ success: boolean, removed: number, errors: Array<string> }}
   */
  async cleanupAll() {
    const result = { success: true, removed: 0, errors: [] };

    try {
      const worktrees = await this.listWorktrees();
      const harnessWorktrees = worktrees.filter((wt) =>
        wt.path.startsWith(this.harnessDir)
      );

      if (harnessWorktrees.length === 0) {
        console.log(`${LOG_PREFIX} No harness worktrees to clean up`);
        return result;
      }

      console.log(`${LOG_PREFIX} Cleaning up ${harnessWorktrees.length} harness worktrees`);

      for (const wt of harnessWorktrees) {
        // Extract task ID from path (last path segment)
        const taskId = path.basename(wt.path);

        try {
          await this.removeWorktree(taskId);
          result.removed++;
        } catch (err) {
          console.error(`${LOG_PREFIX} Failed to remove worktree ${taskId}: ${err.message}`);
          result.errors.push(`${taskId}: ${err.message}`);
          result.success = false;
        }
      }

      console.log(`${LOG_PREFIX} Cleanup complete: ${result.removed} removed, ${result.errors.length} errors`);
      return result;
    } catch (err) {
      console.error(`${LOG_PREFIX} Cleanup failed: ${err.message}`);
      result.success = false;
      result.errors.push(err.message);
      return result;
    }
  }
}

// Export singleton
module.exports = new WorktreeManager();
