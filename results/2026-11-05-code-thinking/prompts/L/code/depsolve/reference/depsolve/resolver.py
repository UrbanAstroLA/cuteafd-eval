from .errors import CycleError, ResolutionError
from .constraint import Constraint


class _DeadEnd(Exception):
    pass


def resolve(index, requirements):
    first = []

    def dead(name, constraints):
        if not first:
            first.append((name, [(str(c), src) for c, src in constraints[name]]))

    def search(decided, constraints):
        pending = sorted(n for n in constraints if n not in decided)
        if not pending:
            return decided
        name = pending[0]
        cands = [v for v in reversed(index.versions(name)) if all(c.allows(v) for c, _ in constraints[name])]
        if not cands:
            dead(name, constraints)
            return None
        for v in cands:
            new_decided = dict(decided)
            new_decided[name] = v
            new_constraints = {k: list(lst) for k, lst in constraints.items()}
            ok = True
            for dep, c in sorted(index.dependencies(name, v).items()):
                new_constraints.setdefault(dep, []).append((c, f"{name} {v}"))
                if dep in new_decided and not c.allows(new_decided[dep]):
                    dead(dep, new_constraints)
                    ok = False
                    break
            if not ok:
                continue
            ans = search(new_decided, new_constraints)
            if ans is not None:
                return ans
        return None

    init = {}
    for name, text in sorted(requirements.items()):
        init.setdefault(name, []).append((Constraint.parse(text), "root"))
    ans = search({}, init)
    if ans is None:
        raise ResolutionError(*first[0])
    return {k: ans[k] for k in sorted(ans)}


def install_order(index, solution):
    deps = {n: [d for d in index.dependencies(n, v) if d in solution] for n, v in solution.items()}
    placed, order = set(), []
    while True:
        ready = sorted(n for n in solution if n not in placed and all(d in placed for d in deps[n]))
        if not ready:
            break
        order.append(ready[0])
        placed.add(ready[0])
    left = [n for n in solution if n not in placed]
    if left:
        raise CycleError(left)
    return order
