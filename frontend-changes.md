# Frontend Code Quality Tools

This document describes the code quality tools added to the frontend development workflow.

## Overview

The following tools have been integrated into the frontend:

- **ESLint** - JavaScript linting for code quality and consistency
- **Prettier** - Automatic code formatting for JS, CSS, HTML, and JSON
- **Stylelint** - CSS linting for consistent styles

## Files Added

| File | Purpose |
|------|---------|
| `frontend/package.json` | NPM package configuration with scripts and dependencies |
| `frontend/eslint.config.js` | ESLint 9+ flat config for JavaScript linting |
| `frontend/.prettierrc` | Prettier formatting configuration |
| `frontend/.prettierignore` | Files to exclude from Prettier formatting |
| `frontend/.stylelintrc.json` | Stylelint rules for CSS linting |
| `frontend/.editorconfig` | Editor-agnostic formatting settings |
| `frontend/quality-check.sh` | Shell script for running quality checks |

## NPM Scripts

Run these commands from the `frontend/` directory:

```bash
# Check for issues (no changes)
npm run lint          # ESLint check
npm run stylelint     # Stylelint check
npm run format:check  # Prettier check
npm run quality       # Run all checks

# Fix issues automatically
npm run lint:fix      # ESLint with auto-fix
npm run stylelint:fix # Stylelint with auto-fix
npm run format        # Prettier format all files
npm run quality:fix   # Run all fixes
```

## Shell Script

A convenience script is provided for quick quality checks:

```bash
# Check mode (reports issues)
./quality-check.sh

# Fix mode (auto-fixes issues)
./quality-check.sh --fix
```

## Configuration Details

### ESLint Rules

- **Best practices**: strict equality, no unused vars, limited console usage
- **Style consistency**: semicolons, single quotes, 4-space indentation
- **ES6+**: prefer const, no var, arrow function spacing

### Prettier Settings

- 4-space indentation
- Single quotes
- Trailing commas
- 100 character line width
- LF line endings

### Stylelint Rules

- Extends `stylelint-config-standard`
- Allows camelCase selectors for existing code compatibility
- Legacy color function notation for browser compatibility

## Getting Started

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Run quality checks:
   ```bash
   npm run quality
   ```

3. Fix any issues:
   ```bash
   npm run quality:fix
   ```

## Editor Integration

The `.editorconfig` file ensures consistent settings across different editors. Most editors support EditorConfig natively or via plugins.

For the best experience, install editor extensions for:
- ESLint
- Prettier
- Stylelint
- EditorConfig
