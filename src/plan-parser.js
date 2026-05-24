/**
 * PlanParser — Parses Cline plan output into structured execution plans.
 *
 * Handles extracting JSON from Cline's plan mode responses, validating
 * the plan structure, building phased execution schedules, and generating
 * task-specific prompts.
 *
 * Exports a singleton instance.
 */

const LOG_PREFIX = '[PlanParser]';

const CODE_REVIEW_PROMPT = `Review the code changes in this worktree for:
1. Correctness — does it do what the task requires?
2. Simplicity — no over-engineering, minimum code for the job
3. Style consistency — matches the project's existing patterns
4. No orphan imports, variables, or dead code
5. Proper error handling

Report any issues found and whether the code passes review.`;

/**
 * Try to extract a JSON object/array from a text blob.
 * Cline often wraps JSON in markdown code fences or prose.
 */
function _extractJSON(text) {
  // Try direct parse first
  try {
    return JSON.parse(text);
  } catch {
    // Try to find JSON in markdown code fences
    const codeBlockMatch = text.match(/```(?:json)?\s*\n([\s\S]*?)\n```/);
    if (codeBlockMatch) {
      try {
        return JSON.parse(codeBlockMatch[1]);
      } catch {
        // fall through
      }
    }

    // Try to find the outermost balanced JSON object
    const braceStart = text.indexOf('{');
    if (braceStart !== -1) {
      let depth = 0;
      let inString = false;
      let escaped = false;
      for (let i = braceStart; i < text.length; i++) {
        const ch = text[i];
        if (escaped) {
          escaped = false;
          continue;
        }
        if (ch === '\\') {
          escaped = true;
          continue;
        }
        if (ch === '"') {
          inString = !inString;
          continue;
        }
        if (!inString) {
          if (ch === '{') depth++;
          if (ch === '}') {
            depth--;
            if (depth === 0) {
              try {
                return JSON.parse(text.slice(braceStart, i + 1));
              } catch {
                break;
              }
            }
          }
        }
      }
    }
  }
  return null;
}

/**
 * Try to extract a JSON array from text (for task lists).
 */
function _extractJSONArray(text) {
  // Try direct parse
  try {
    const arr = JSON.parse(text);
    if (Array.isArray(arr)) return arr;
  } catch {
    // Try code fences
    const codeBlockMatch = text.match(/```(?:json)?\s*\n([\s\S]*?)\n```/);
    if (codeBlockMatch) {
      try {
        const arr = JSON.parse(codeBlockMatch[1]);
        if (Array.isArray(arr)) return arr;
      } catch {
        // fall through
      }
    }

    // Try bracket matching
    const bracketStart = text.indexOf('[');
    if (bracketStart !== -1) {
      let depth = 0;
      let inString = false;
      let escaped = false;
      for (let i = bracketStart; i < text.length; i++) {
        const ch = text[i];
        if (escaped) {
          escaped = false;
          continue;
        }
        if (ch === '\\') {
          escaped = true;
          continue;
        }
        if (ch === '"') {
          inString = !inString;
          continue;
        }
        if (!inString) {
          if (ch === '[') depth++;
          if (ch === ']') {
            depth--;
            if (depth === 0) {
              try {
                const arr = JSON.parse(text.slice(bracketStart, i + 1));
                if (Array.isArray(arr)) return arr;
              } catch {
                break;
              }
            }
          }
        }
      }
    }
  }
  return null;
}

/**
 * Normalize a raw plan into a standard shape.
 * Expected output: { design, tasks: [{ id, description, files, dependencies }] }
 */
function _normalizePlan(raw) {
  const plan = { design: '', tasks: [] };

  // Extract design/overview
  plan.design = raw.design || raw.overview || raw.summary || raw.description || '';

  // Extract tasks
  let tasks = raw.tasks || raw.steps || raw.phases || raw.items || [];
  if (!Array.isArray(tasks)) {
    console.warn(`${LOG_PREFIX} Plan tasks field is not an array`);
    return plan;
  }

  plan.tasks = tasks.map((t, idx) => ({
    id: t.id || `task-${idx + 1}`,
    description: t.description || t.title || t.name || t.prompt || `Task ${idx + 1}`,
    files: t.files || t.changedFiles || t.paths || [],
    dependencies: t.dependencies || t.dependsOn || t.after || [],
    phase: t.phase || undefined,
  }));

  return plan;
}

class PlanParser {
  /**
   * Parse raw Cline plan output into a structured plan object.
   * @param {string} text - Raw text from Cline's plan mode
   * @returns {{ design: string, tasks: Array }}
   */
  parsePlanOutput(text) {
    console.log(`${LOG_PREFIX} Parsing plan output (${text.length} chars)`);

    const raw = _extractJSON(text);
    if (!raw) {
      console.warn(`${LOG_PREFIX} Could not extract JSON from plan output, using fallback`);
      // Fallback: treat entire text as a single task
      return {
        design: text.slice(0, 500),
        tasks: [
          {
            id: 'task-1',
            description: text,
            files: [],
            dependencies: [],
          },
        ],
      };
    }

    // If it's an array directly, wrap it
    if (Array.isArray(raw)) {
      return _normalizePlan({ tasks: raw });
    }

    return _normalizePlan(raw);
  }

  /**
   * Validate a parsed plan. Checks for required fields and circular dependencies.
   * @param {{ design: string, tasks: Array }} plan
   * @returns {{ valid: boolean, errors: Array<string> }}
   */
  validatePlan(plan) {
    const errors = [];

    if (!plan || typeof plan !== 'object') {
      return { valid: false, errors: ['Plan is null or not an object'] };
    }

    if (!plan.tasks || !Array.isArray(plan.tasks)) {
      errors.push('Plan missing tasks array');
      return { valid: false, errors };
    }

    if (plan.tasks.length === 0) {
      errors.push('Plan has zero tasks');
      return { valid: false, errors };
    }

    const taskIds = new Set(plan.tasks.map((t) => t.id));

    // Check for duplicate IDs
    if (taskIds.size !== plan.tasks.length) {
      errors.push('Duplicate task IDs found');
    }

    // Check dependencies reference valid tasks
    for (const task of plan.tasks) {
      if (!task.id) {
        errors.push('Task missing id field');
        continue;
      }
      if (!task.description) {
        errors.push(`Task ${task.id} missing description`);
      }
      if (!Array.isArray(task.dependencies)) {
        errors.push(`Task ${task.id} dependencies is not an array`);
        continue;
      }
      for (const dep of task.dependencies) {
        if (!taskIds.has(dep)) {
          errors.push(`Task ${task.id} depends on unknown task: ${dep}`);
        }
      }
    }

    // Check for circular dependencies using topological sort
    if (errors.length === 0) {
      const visited = new Set();
      const inStack = new Set();

      function hasCycle(taskId) {
        if (inStack.has(taskId)) return true;
        if (visited.has(taskId)) return false;
        inStack.add(taskId);
        const task = plan.tasks.find((t) => t.id === taskId);
        if (task && task.dependencies) {
          for (const dep of task.dependencies) {
            if (hasCycle(dep)) return true;
          }
        }
        inStack.delete(taskId);
        visited.add(taskId);
        return false;
      }

      for (const task of plan.tasks) {
        if (hasCycle(task.id)) {
          errors.push('Circular dependency detected among tasks');
          break;
        }
      }
    }

    return { valid: errors.length === 0, errors };
  }

  /**
   * Build a phased execution plan from a validated plan.
   * Tasks with no unmet dependencies can run in parallel within a phase.
   * @param {{ design: string, tasks: Array }} plan
   * @returns {{ phases: Array<{ phase: number, tasks: Array }> }}
   */
  buildExecutionPlan(plan) {
    const phases = [];
    const completed = new Set();
    const remaining = new Map(plan.tasks.map((t) => [t.id, t]));

    while (remaining.size > 0) {
      // Find tasks whose dependencies are all completed
      const ready = [];
      for (const [id, task] of remaining) {
        const deps = task.dependencies || [];
        if (deps.every((d) => completed.has(d))) {
          ready.push({ ...task });
        }
      }

      if (ready.length === 0) {
        // This shouldn't happen if validation passed (no cycles)
        console.warn(`${LOG_PREFIX} No ready tasks found but ${remaining.size} remaining — possible cycle`);
        break;
      }

      phases.push({
        phase: phases.length + 1,
        tasks: ready,
      });

      for (const task of ready) {
        completed.add(task.id);
        remaining.delete(task.id);
      }
    }

    return { phases };
  }

  /**
   * Generate a prompt for a specific task within a plan.
   * Combines the task description with plan context.
   * @param {{ id: string, description: string }} task
   * @param {{ design: string, tasks: Array }} plan
   * @returns {string}
   */
  getTaskPrompt(task, plan) {
    const lines = [];

    if (plan.design) {
      lines.push(`## Project Context\n${plan.design}\n`);
    }

    lines.push(`## Your Task\n${task.description}\n`);

    // List dependency info
    if (task.dependencies && task.dependencies.length > 0) {
      const depTasks = plan.tasks.filter((t) =>
        task.dependencies.includes(t.id)
      );
      lines.push('## Dependencies (already completed)');
      for (const dep of depTasks) {
        lines.push(`- ${dep.id}: ${dep.description}`);
      }
      lines.push('');
    }

    return lines.join('\n');
  }

  /**
   * Generate a checklist summary string for the plan.
   * @param {{ design: string, tasks: Array }} plan
   * @returns {string}
   */
  generateChecklist(plan) {
    if (!plan || !plan.tasks) return 'No tasks in plan.';

    const lines = [`Plan: ${plan.design || 'Untitled'}`, ''];
    for (const task of plan.tasks) {
      const deps = task.dependencies && task.dependencies.length
        ? ` (depends on: ${task.dependencies.join(', ')})`
        : '';
      lines.push(`- [ ] **${task.id}**: ${task.description}${deps}`);
    }
    return lines.join('\n');
  }

  /**
   * Get the code review prompt.
   * @returns {string}
   */
  getCodeReviewPrompt() {
    return CODE_REVIEW_PROMPT;
  }
}

module.exports = new PlanParser();
