import random

import pytest

from depsolve import (Constraint, CycleError, DepError, Index, ResolutionError, Version, install_order,
                      resolve)


def V(s):
    return Version.parse(s)


def make_index(spec):
    idx = Index()
    for name, versions in spec.items():
        for ver, deps in versions.items():
            idx.add(name, ver, deps)
    return idx


def as_str(solution):
    return {k: str(v) for k, v in solution.items()}


# ---- versions ----

def test_version_parse_fields_and_str():
    v = V("1.20.3-alpha.1.x-y")
    assert (v.major, v.minor, v.patch) == (1, 20, 3)
    assert v.prerelease == ("alpha", 1, "x-y")
    assert str(v) == "1.20.3-alpha.1.x-y"
    assert V("0.0.0").prerelease == ()
    assert Version(1, 2, 3) == V("1.2.3")
    assert Version(1, 0, 0, ("rc", 1)) == V("1.0.0-rc.1")
    assert len({V("1.2.3"), Version(1, 2, 3), V("1.2.4")}) == 2


def test_version_is_immutable():
    v = V("1.2.3")
    with pytest.raises(Exception):
        v.major = 5


def test_version_precedence_chain():
    chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
             "1.0.0-rc.1", "1.0.0", "1.0.1", "1.9.0", "1.10.0", "2.0.0"]
    shuffled = chain[:]
    random.Random(7).shuffle(shuffled)
    assert [str(v) for v in sorted(V(s) for s in shuffled)] == chain
    assert V("1.0.0-2") < V("1.0.0-10") < V("1.0.0-1a") < V("1.0.0-a")
    assert V("1.0.0-rc.1") <= V("1.0.0-rc.1") and V("2.0.0") > V("1.99.99") and V("1.0.0") != V("1.0.0-0")


def test_version_invalid():
    for text in ["1.2", "01.2.3", "1.02.3", "1.2.3-01", "1.2.3-", "1.2.3-a..b", "1.2.3+build", " 1.2.3", "1.2.3.4",
                 "v1.2.3", "1.2.3-a_b", ""]:
        with pytest.raises(ValueError):
            Version.parse(text)


# ---- constraints ----

def check(constraint, yes, no):
    c = Constraint.parse(constraint)
    for v in yes:
        assert c.allows(V(v)), (constraint, v)
    for v in no:
        assert not c.allows(V(v)), (constraint, v)


def test_basic_comparators_and_partials():
    check(">=1.2,<2", ["1.2.0", "1.9.9"], ["1.1.9", "2.0.0"])
    check(">1.2", ["1.2.1"], ["1.2.0"])
    check("<=1.2", ["1.2.0", "0.1.0"], ["1.2.1"])
    check("==1.4.0", ["1.4.0"], ["1.4.1"])
    check("!=1.4.0, >=1", ["1.0.0", "1.4.1"], ["1.4.0", "0.9.0"])
    check("*", ["0.0.0", "99.0.0"], [])


def test_caret():
    check("^1.4.2", ["1.4.2", "1.99.0"], ["1.4.1", "2.0.0"])
    check("^1.4", ["1.4.0", "1.9.0"], ["1.3.9", "2.0.0"])
    check("^0.4.2", ["0.4.2", "0.4.9"], ["0.4.1", "0.5.0"])
    check("^0.0.4", ["0.0.4"], ["0.0.3", "0.0.5"])
    check("^0", ["0.0.0", "0.9.9"], ["1.0.0"])
    check("^0.0", ["0.0.9"], ["0.1.0"])
    check("^0.4", ["0.4.0", "0.4.7"], ["0.5.0"])
    check("^0.0.0", ["0.0.0"], ["0.0.1"])


def test_tilde():
    check("~1.4.2", ["1.4.2", "1.4.9"], ["1.4.1", "1.5.0"])
    check("~1.4", ["1.4.0"], ["1.5.0", "1.3.0"])
    check("~1", ["1.0.0", "1.9.0"], ["2.0.0", "0.9.0"])


def test_prerelease_rule():
    check(">=1.0.0", ["1.1.0"], ["1.1.0-rc.1"])
    check(">=1.1.0-alpha", ["1.1.0-rc.1", "1.1.0-alpha", "1.2.0"], ["1.2.0-rc.1", "1.1.0-0"])
    check("<2.0.0", ["1.9.9"], ["2.0.0-rc.1"])
    check("*", [], ["1.0.0-beta"])
    check("^1.4.0-beta", ["1.4.0-beta.2", "1.4.0", "1.8.0"], ["1.4.0-alpha", "1.5.0-beta"])
    check("==1.0.0-rc.1", ["1.0.0-rc.1"], ["1.0.0-rc.2", "1.0.0"])


def test_constraint_str_and_string_versions():
    c = Constraint.parse("  >= 1.2 ,<2  ")
    assert str(c) == ">=1.2,<2"
    assert str(Constraint.parse("^ 0.3")) == "^0.3"
    assert c.allows("1.5.0") and not c.allows("2.0.0")


def test_constraint_invalid():
    for text in ["", "1.2.3", "==1.2", "=>1", ">=1,,<2", ">=", "^1.2.3.4", "~01", ">=1.x", "<1.2-rc.1", ">=1,"]:
        with pytest.raises(ValueError):
            Constraint.parse(text)


# ---- index ----

def test_index_versions_and_dependencies():
    idx = Index()
    idx.add("lib", "1.10.0")
    idx.add("lib", "1.2.0-rc.1")
    idx.add("lib", "1.2.0", {"zlib": "^1", "abc": ">=0.1"})
    assert [str(v) for v in idx.versions("lib")] == ["1.2.0-rc.1", "1.2.0", "1.10.0"]
    assert idx.versions("nope") == []
    deps = idx.dependencies("lib", "1.2.0")
    assert list(deps) == ["abc", "zlib"]
    assert isinstance(deps["zlib"], Constraint) and str(deps["zlib"]) == "^1"
    assert idx.dependencies("lib", V("1.10.0")) == {}
    with pytest.raises(KeyError):
        idx.dependencies("lib", "9.9.9")


def test_index_rejects_bad_adds():
    idx = Index()
    idx.add("a", "1.0.0")
    with pytest.raises(ValueError):
        idx.add("a", "1.0.0", {"b": "*"})
    with pytest.raises(ValueError):
        idx.add("a", "2.0.0", {"a": "^1"})
    with pytest.raises(ValueError):
        idx.add("a", "1.0", {})
    with pytest.raises(ValueError):
        idx.add("b", "1.0.0", {"c": "1.0.0"})


# ---- resolver ----

def test_resolve_picks_highest_satisfying():
    idx = make_index({
        "app": {"1.0.0": {"lib": ">=2"}, "1.2.0": {"lib": ">=2.1,<3"}, "2.0.0": {}},
        "lib": {"2.0.0": {}, "2.1.0": {}, "2.5.0": {}, "2.6.0-beta.1": {}, "3.0.0": {}},
    })
    sol = resolve(idx, {"app": "^1.0"})
    assert as_str(sol) == {"app": "1.2.0", "lib": "2.5.0"}
    assert all(isinstance(v, Version) for v in sol.values())
    assert resolve(idx, {}) == {}


def test_resolve_result_keys_sorted():
    idx = make_index({"zed": {"1.0.0": {"mid": "*"}}, "mid": {"1.0.0": {"alpha": "*"}}, "alpha": {"0.1.0": {}}})
    assert list(resolve(idx, {"zed": "*"})) == ["alpha", "mid", "zed"]


def test_resolve_backtracks():
    idx = make_index({
        "a": {"1.0.0": {"c": ">=1"}, "2.0.0": {"c": "<2"}},
        "b": {"1.0.0": {"c": ">=2"}},
        "c": {"1.0.0": {}, "2.0.0": {}, "2.1.0": {}},
    })
    assert as_str(resolve(idx, {"a": "*", "b": "*"})) == {"a": "1.0.0", "b": "1.0.0", "c": "2.1.0"}


def test_resolve_skips_candidate_conflicting_with_decided():
    idx = make_index({
        "b": {"1.0.0": {}, "2.0.0": {}},
        "z": {"1.0.0": {"b": ">=1"}, "2.0.0": {"b": "==2.0.0"}},
    })
    assert as_str(resolve(idx, {"b": "==1.0.0", "z": "*"})) == {"b": "1.0.0", "z": "1.0.0"}


def test_conflict_message_format():
    idx = make_index({
        "x": {"1.0.0": {"z": "<2"}},
        "y": {"1.0.0": {"z": ">= 2"}},
        "z": {"1.0.0": {}, "2.0.0": {}},
    })
    with pytest.raises(ResolutionError) as ei:
        resolve(idx, {"y": "^1", "x": "^1", "z": "!=1.5.0"})
    err = ei.value
    assert err.package == "z"
    assert err.constraints == [("!=1.5.0", "root"), ("<2", "x 1.0.0"), (">=2", "y 1.0.0")]
    assert str(err) == "conflict on z: !=1.5.0 (from root), <2 (from x 1.0.0), >=2 (from y 1.0.0)"
    assert isinstance(err, DepError)


def test_conflict_on_decided_package():
    idx = make_index({"b": {"1.0.0": {}, "2.0.0": {}}, "z": {"2.0.0": {"b": "==2.0.0"}}})
    with pytest.raises(ResolutionError) as ei:
        resolve(idx, {"b": "==1.0.0", "z": "*"})
    assert ei.value.package == "b"
    assert ei.value.constraints == [("==1.0.0", "root"), ("==2.0.0", "z 2.0.0")]


def test_first_dead_end_is_reported():
    idx = make_index({
        "a": {"1.0.0": {"d": "*"}, "2.0.0": {"c": "<2"}},
        "b": {"1.0.0": {"c": ">=2"}},
        "c": {"1.0.0": {}, "2.0.0": {}},
    })
    with pytest.raises(ResolutionError) as ei:
        resolve(idx, {"a": "*", "b": "*"})
    assert ei.value.package == "c"
    assert ei.value.constraints == [("<2", "a 2.0.0"), (">=2", "b 1.0.0")]


def test_unknown_package_and_prerelease_resolution():
    with pytest.raises(ResolutionError) as ei:
        resolve(Index(), {"nope": "*"})
    assert str(ei.value) == "conflict on nope: * (from root)"
    idx = make_index({"lib": {"1.0.0": {}, "1.1.0-rc.1": {}}})
    assert as_str(resolve(idx, {"lib": ">=1"})) == {"lib": "1.0.0"}
    assert as_str(resolve(idx, {"lib": ">=1.1.0-rc.0"})) == {"lib": "1.1.0-rc.1"}


# ---- install order ----

def test_install_order_ties_by_name():
    idx = make_index({
        "app": {"1.0.0": {"lib": "*", "util": "*"}},
        "lib": {"1.0.0": {"util": "*"}},
        "util": {"1.0.0": {}},
        "zeta": {"1.0.0": {}},
        "alpha": {"1.0.0": {"zeta": "*"}},
    })
    sol = resolve(idx, {"app": "*", "alpha": "*"})
    assert install_order(idx, sol) == ["util", "lib", "app", "zeta", "alpha"]


def test_install_order_cycle():
    idx = make_index({
        "a": {"1.0.0": {"b": "*"}},
        "b": {"1.0.0": {"a": "^1"}},
        "c": {"1.0.0": {"a": "*"}},
        "d": {"1.0.0": {}},
    })
    sol = resolve(idx, {"c": "*", "d": "*"})
    assert as_str(sol) == {"a": "1.0.0", "b": "1.0.0", "c": "1.0.0", "d": "1.0.0"}
    with pytest.raises(CycleError) as ei:
        install_order(idx, sol)
    assert ei.value.packages == ["a", "b", "c"]
