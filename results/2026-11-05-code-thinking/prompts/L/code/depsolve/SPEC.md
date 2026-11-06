Build a Python package named `depsolve`: semantic versions, version constraints, a package index and a backtracking dependency resolver. Python 3.12, standard library only.

## Files

- `depsolve/__init__.py` — re-exports `Version`, `Constraint`, `Index`, `resolve`, `install_order`, `DepError`, `ResolutionError`, `CycleError`.
- `depsolve/errors.py` — the exception classes.
- `depsolve/version.py` — `Version`.
- `depsolve/constraint.py` — `Constraint`.
- `depsolve/index.py` — `Index`.
- `depsolve/resolver.py` — `resolve` and `install_order`.

## errors.py

- `DepError(Exception)` — base class.
- `ResolutionError(DepError)` — `ResolutionError(package, constraints)`; attributes `package` (str) and `constraints`, a list of `(text, source)` pairs. `str(err)` is `f"conflict on {package}: "` plus the pairs as `f"{text} (from {source})"` joined with `", "`.
- `CycleError(DepError)` — `CycleError(packages)`; attribute `packages` (sorted list of names).

## version.py

`Version(major, minor, patch, prerelease=())` is immutable and hashable, with those attributes; `prerelease` is a tuple of identifiers (numeric ones as `int`, others `str`).

- `Version.parse(text)` accepts exactly `MAJOR.MINOR.PATCH`, optionally followed by `-` and dot-separated non-empty identifiers of `[0-9A-Za-z-]`. Numbers and all-digit identifiers have no leading zeros (`0` is fine). Anything else (whitespace, `+build`, ...) raises `ValueError`.
- `str(v)` gives the canonical text. All comparisons follow semver precedence: major, minor, patch numerically; a pre-release is lower than the same version without; pre-releases compare identifier by identifier (numeric ones numerically, others by ASCII, numeric lower than alphanumeric); if all shared identifiers are equal the shorter list is lower.

## constraint.py

`Constraint.parse(text)` parses one or more comparators separated by `,` (all must hold); whitespace is ignored. A comparator is `*`, or one of `>=`, `>`, `<=`, `<`, `==`, `!=`, `^`, `~` followed by a version: a full one (`Version.parse` syntax), or, except after `==`/`!=`, a partial `MAJOR` or `MAJOR.MINOR` (same number rules). Anything else, including an empty comparator, raises `ValueError`.

Meaning (missing parts of a partial version count as 0):

- `*` matches any version; `>=`, `>`, `<=`, `<`, `==`, `!=` compare.
- `^v` — `>=v` and below `v` with its leftmost non-zero given part (the last given part if all are zero) incremented and later parts 0: `^1.4.2`, `^1.4`, `^1` → `<2.0.0`; `^0.4.2`, `^0.4` → `<0.5.0`; `^0.0.4` → `<0.0.5`; `^0` → `<1.0.0`; `^0.0` → `<0.1.0`.
- `~v` — `>=v` and `<M.(m+1).0` if a minor is given, else `<(M+1).0.0` (`M`, `m`: major, minor of `v`).

Pre-release rule: a pre-release version is allowed only if every comparator holds **and** some comparator's version has a pre-release and the same major, minor and patch. So `>=1.1.0-alpha` allows `1.1.0-rc.1` but not `1.2.0-rc.1`, and `*` allows none.

- `c.allows(version)` — `version` is a `Version` or a string; returns `bool`.
- `str(c)` — the comparators with all whitespace removed, joined with `","` (`" >= 1.2 , <2 "` → `">=1.2,<2"`).

## index.py

`Index()` holds published packages.

- `add(name, version, dependencies=None)` — `version` is a string; `dependencies` maps names to constraint strings. Parse errors propagate (`ValueError`). A duplicate `(name, version)` or a dependency on `name` itself raises `ValueError`.
- `versions(name)` — list of `Version`, ascending; `[]` for an unknown name.
- `dependencies(name, version)` — dict of name → `Constraint`, keys in sorted order. `version` is a `Version` or string. Raises `KeyError` if not published.

## resolver.py

`resolve(index, requirements) -> dict[str, Version]`. `requirements` maps names to constraint strings. The result maps every chosen package to its version, keys sorted.

Depth-first backtracking search over *states*: decided packages (name → version) and, per package, a list of `(Constraint, source)` in the order added. The initial state holds the requirements in sorted name order with source `"root"`. In a state:

1. If no undecided package has constraints, the decisions are the answer.
2. Otherwise take the undecided package with constraints whose name sorts first. Its candidates are its versions allowing all its constraints, highest first. If there are none, the state is a *dead end on that package*.
3. For each candidate `v`, in order: form a new state with the package decided as `v` and each of `v`'s dependencies appended (in sorted name order, source `f"{name} {v}"`). If a dependency names a decided package whose version it does not allow, the new state is a dead end on that dependency (check dependencies in sorted name order, stop at the first). Otherwise search the new state; return its answer if it has one.
4. If no candidate leads to an answer, the state fails.

If the initial state fails, raise `ResolutionError` for the **first** dead end met during the search, with that package's constraint list at that moment (constraint text as `str(c)`).

`install_order(index, solution) -> list[str]` returns the names of `solution` so that every package comes after its dependencies (per the index; names not in `solution` are ignored); among packages whose dependencies are all placed, the smallest name goes next. If some packages cannot be placed because of a dependency cycle, raise `CycleError` with the sorted names of all packages left unplaced.
