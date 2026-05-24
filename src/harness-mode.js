const HARNESS_PRINCIPLES = `# Harness Mode: Code Quality Principles
1. **Think Before Coding**: State assumptions. Ask if unclear. Don't hide confusion.
2. **Simplicity First**: Minimum code that solves the problem. No speculative features, no single-use abstractions.
3. **Surgical Changes**: Touch ONLY requested code. Match existing style. Clean YOUR mess only (orphan imports/vars).
4. **Goal-Driven**: Transform tasks into verifiable goals (e.g., pass tests). Loop until met.`;

const HARNESS_WORKFLOW_PROMPT = `# Harness Mode: Workflow & Code Quality

## Harness 4 Principles
1. **Think Before Coding**: State assumptions. Ask if unclear. Don't hide confusion.
2. **Simplicity First**: Minimum code that solves the problem. No speculative features, no single-use abstractions.
3. **Surgical Changes**: Touch ONLY requested code. Match existing style. Clean YOUR mess only (orphan imports/vars).
4. **Goal-Driven**: Transform tasks into verifiable goals (e.g., pass tests). Loop until met.

## Plan-First Requirement
- **Always start with plan mode**. Before writing any code, analyze the request, identify the scope, and produce a structured plan.
- Do not jump directly into implementation — planning reduces rework and clarifies dependencies.

## Task Breakdown & Independence
- Output a structured JSON plan with design overview + task breakdown.
- **Each task must be independent and simple** — aim for tasks that can be completed in a single focused session.
- Tasks should have clear inputs, outputs, and acceptance criteria.
- Avoid tasks that require simultaneous changes across multiple unrelated modules.

## Parallel Development with Git Worktree
- Consider **parallel development** where tasks are truly independent.
- Use **git worktree** to create separate working directories for parallel task branches.
- Design task boundaries to minimize merge conflicts when tasks converge.
- If tasks share code, extract the shared interface first as its own task.

## Code Review + QA Requirement
- **Every task requires a code review pass** after development — check for simplicity, correctness, and style consistency.
- **Every task requires QA testing** — run relevant tests, verify behavior, and confirm acceptance criteria are met.
- Do not mark a task complete until both review and QA pass.`;

class HarnessMode {
  constructor() {
    // Default enabled; overridden by env var check in isEnabled()
    this.enabled = null;
  }

  /**
   * Check if harness mode is enabled via the HARNESS_MODE env var.
   * Returns true if HARNESS_MODE is set to "1", "true", or "on" (case-insensitive).
   * Returns false if set to "0", "false", "off", or undefined/unset.
   */
  isEnabled() {
    if (this.enabled !== null) {
      return this.enabled;
    }
    const val = (process.env.HARNESS_MODE || '').toLowerCase().trim();
    this.enabled = ['1', 'true', 'on'].includes(val);
    return this.enabled;
  }

  /**
   * Returns the core 4 harness principles string.
   */
  getPrinciples() {
    return HARNESS_PRINCIPLES;
  }

  /**
   * Returns the full harness workflow system prompt (principles + workflow rules).
   */
  getWorkflowPrompt() {
    return HARNESS_WORKFLOW_PROMPT;
  }

  /**
   * Inject the harness 4 principles into the given prompt (backward compatible).
   * Appends the principles section if harness mode is enabled.
   */
  injectPrinciples(prompt) {
    if (!this.isEnabled()) {
      return prompt;
    }
    return `${prompt}\n\n${HARNESS_PRINCIPLES}`;
  }

  /**
   * Inject the full workflow prompt into the given task prompt.
   * Appends the workflow section (principles + plan-first + task breakdown + worktree + review/QA).
   */
  injectWorkflowPrinciples(prompt) {
    if (!this.isEnabled()) {
      return prompt;
    }
    return `${prompt}\n\n${HARNESS_WORKFLOW_PROMPT}`;
  }
}

module.exports = new HarnessMode();
