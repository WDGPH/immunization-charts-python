# Code Analysis Standards

This document defines procedures for analyzing code to detect dead code, duplicates, and ensure real-world significance during rapid pre-v1.0 development.

## Why Code Analysis Matters

In rapid development, code can accumulate dead functions, duplicates, and unclear dependencies. This guide provides systematic procedures to catch these issues before they become technical debt.

## Code Analysis Checklist

When analyzing any function or module, follow this checklist:

### 1. Functional Analysis

**Question:** Is this code actually being used and what does it affect?

```bash
# Find where a function is defined
grep -n "def function_name" scripts/*.py

# Find where it's called
grep -r "function_name" scripts/*.py tests/*.py

# Check if it's imported anywhere
grep -r "from .* import.*function_name\|import.*function_name" scripts/*.py tests/*.py

# Trace through run_pipeline.py to see what output it affects
grep -A 50 "run_pipeline.main()" scripts/run_pipeline.py
```

**Real questions to answer:**
- [ ] **Where is this called?** – List all call sites
- [ ] **What does it do with the results?** – Trace to final output
- [ ] **What are the side effects?** – File I/O, config reads, logging?
- [ ] **Is it on the critical path?** – Steps 1-6 (core) vs Steps 7-9 (optional)
- [ ] **Is it actually used or dead?** – Test-only functions? Disabled features?

### 2. Dead Code Detection

**Dead code indicators:**
- Function is defined but never called outside of tests
- Only called from commented-out code
- Parameter is optional and never actually passed
- Try/except that catches everything and silently ignores
- TODO comments indicating unfinished work

**Detection procedure:**
```bash
# Find all function definitions
grep -n "def " scripts/*.py | grep -v "__"

# For each function, search for callers
grep -r "function_name(" scripts/*.py tests/*.py

# If not found, check if it's called dynamically
grep -r "getattr.*function_name\|__dict__" scripts/*.py
```

**Action when found:**
- Remove it if clearly dead
- Ask: "Why does this exist if it's unused?"

### 3. Duplication Analysis

**Duplication indicators:**
- Similar function names or signatures
- Identical or nearly-identical logic in multiple files
- Similar patterns (date parsing, template rendering, grouping)
- Multiple implementations of the same algorithm
- Copy-paste code with minor modifications

**Detection procedure:**
```bash
# Look for similar function names
grep "def.*template.*\|def.*render.*\|def.*format.*" scripts/*.py

# Look for similar patterns (e.g., date parsing)
grep -n "strptime\|strftime\|datetime" scripts/*.py

# Compare line counts (modules >300 lines might have duplication)
wc -l scripts/*.py | sort -n

# Look for identical blocks
grep -n "for .* in .*clients\|for .* in .*rows" scripts/*.py
```

**Action when found:**
- Extract to `utils.py` ONLY if:
  1. Used by 2+ modules (not just one)
  2. Doesn't introduce new dependencies
- Otherwise, colocate with the primary user

### 4. Real-World Significance Analysis

**Question:** If this breaks, what happens to the user's immunization notices?

For every function, ask:

- [ ] **What output does this affect?** – PDF content, JSON structure, file path?
- [ ] **Is it on the critical path?** – Steps 1-6: yes/no
- [ ] **Does it affect determinism?** – Same input → same output?
- [ ] **Does it affect data integrity?** – Could it corrupt notices?
- [ ] **Would a user notice if this broke?** – Or does it only affect logging?

## Rapid Change Protocol

**Before making any code changes:**

1. **Search for all usages** of the function/module being modified
   ```bash
   grep -r "function_name\|class_name" scripts/ tests/
   ```

2. **Trace side effects** (file I/O, config reads, logging)
   ```bash
   # Look for open(), read(), write(), load_config()
   grep -n "open\|read\|write\|load_config\|logging" scripts/my_module.py
   ```

3. **Check for duplicates** with similar functionality
   ```bash
   grep -r "similar.*pattern" scripts/*.py
   ```

4. **Check for dead code** (test-only, disabled, experimental)
   ```bash
   grep -n "TODO\|FIXME\|disabled\|deprecated" scripts/*.py
   ```

5. **Verify it's on the critical path** (Step 1-6, not experimental)
   - If Steps 7-9 only: lower priority
   - If Steps 1-6: high priority

## Key Questions to Answer

1. **Is this function used?** – Search for all call sites
2. **Where does its output go?** – Trace to final artifact
3. **Is this duplicated elsewhere?** – Search for similar patterns
4. **If it breaks, what fails?** – Understand real-world impact
5. **Should this be extracted?** – Only if 2+ modules use it

## Recommended Tools

```bash
# GNU grep (built-in on Linux/Mac)
grep -r "pattern" directory/

# ripgrep (faster, recommended)
rg "pattern" directory/

# find combined with grep
find scripts/ -name "*.py" -exec grep -l "function_name" {} \;

# Simple line counts
wc -l scripts/*.py | sort -n
``` 