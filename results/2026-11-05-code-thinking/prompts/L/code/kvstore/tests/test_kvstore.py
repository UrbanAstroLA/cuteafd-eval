import json

import pytest

from kvstore import Interpreter, KVError, Store, TransactionError, dump, load


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(clock):
    return Store(clock=clock)


def test_set_get_delete(store):
    store.set("a", "1")
    assert store.get("a") == "1"
    assert store.get("missing") is None
    assert store.delete("a") is True
    assert store.delete("a") is False
    assert store.get("a") is None


def test_overwrite(store):
    store.set("a", "1")
    store.set("a", "2")
    assert store.get("a") == "2"


def test_count_and_keys(store):
    for k, v in [("b", "x"), ("a", "x"), ("ab", "y"), ("c", "x")]:
        store.set(k, v)
    assert store.count("x") == 3
    assert store.count("zzz") == 0
    assert store.keys() == ["a", "ab", "b", "c"]
    assert store.keys("a") == ["a", "ab"]


def test_ttl_expiry(store, clock):
    store.set("t", "v", ttl=10)
    assert store.ttl("t") == pytest.approx(10)
    clock.advance(9.5)
    assert store.get("t") == "v"
    clock.advance(0.5)
    assert store.get("t") is None
    assert store.keys() == []
    assert store.count("v") == 0
    assert store.ttl("t") == -1
    assert store.delete("t") is False


def test_ttl_none_and_missing(store):
    store.set("p", "v")
    assert store.ttl("p") is None
    assert store.ttl("nope") == -1


def test_set_replaces_expiry(store, clock):
    store.set("k", "v", ttl=5)
    store.set("k", "w")
    clock.advance(100)
    assert store.get("k") == "w"


def test_invalid_ttl(store):
    with pytest.raises(ValueError):
        store.set("k", "v", ttl=0)
    with pytest.raises(ValueError):
        store.set("k", "v", ttl=-1)


def test_transaction_rollback(store):
    store.set("a", "1")
    store.begin()
    store.set("a", "2")
    store.set("b", "3")
    store.delete("a")
    assert store.get("a") is None
    assert store.depth == 1
    store.rollback()
    assert store.depth == 0
    assert store.get("a") == "1"
    assert store.get("b") is None


def test_nested_rollback_inner_only(store):
    store.begin()
    store.set("a", "1")
    store.begin()
    store.set("a", "2")
    assert store.get("a") == "2"
    store.rollback()
    assert store.get("a") == "1"
    store.rollback()
    assert store.get("a") is None


def test_commit_closes_all(store):
    store.begin()
    store.set("a", "1")
    store.begin()
    store.set("b", "2")
    store.commit()
    assert store.depth == 0
    with pytest.raises(TransactionError):
        store.rollback()
    assert store.get("a") == "1" and store.get("b") == "2"


def test_rollback_commit_without_transaction(store):
    with pytest.raises(TransactionError):
        store.rollback()
    with pytest.raises(TransactionError):
        store.commit()
    assert issubclass(TransactionError, KVError)


def test_rollback_restores_expiry(store, clock):
    store.set("k", "v", ttl=10)
    store.begin()
    store.set("k", "w")
    store.rollback()
    assert store.get("k") == "v"
    assert store.ttl("k") == pytest.approx(10)
    clock.advance(10)
    assert store.get("k") is None


def test_count_inside_transaction(store):
    store.set("a", "x")
    store.begin()
    store.set("b", "x")
    assert store.count("x") == 2
    store.rollback()
    assert store.count("x") == 1


def test_snapshot(store, clock):
    store.set("a", "1")
    store.set("b", "2", ttl=5)
    store.set("c", "3", ttl=1)
    clock.advance(2)
    assert store.snapshot() == {"a": {"value": "1", "expires_at": None},
                                "b": {"value": "2", "expires_at": 1005.0}}


def test_dump_load_roundtrip(tmp_path, clock):
    s = Store(clock=clock)
    s.set("a", "1")
    s.set("b", "2", ttl=5)
    s.set("c", "3", ttl=50)
    p = tmp_path / "db.json"
    dump(s, p)
    doc = json.loads(p.read_text())
    assert doc["version"] == 1 and set(doc["items"]) == {"a", "b", "c"}
    clock.advance(10)
    t = load(str(p), clock=clock)
    assert t.keys() == ["a", "c"]
    assert t.ttl("c") == pytest.approx(40)


def test_dump_refuses_open_transaction(tmp_path, store):
    store.begin()
    p = tmp_path / "x.json"
    with pytest.raises(TransactionError):
        dump(store, p)
    assert not p.exists()


def test_load_bad_version(tmp_path):
    p = tmp_path / "v.json"
    p.write_text(json.dumps({"version": 2, "items": {}}))
    with pytest.raises(KVError):
        load(p)


# ---- interpreter ----

@pytest.fixture
def interp(clock):
    return Interpreter(Store(clock=clock))


def test_interp_basic(interp):
    assert interp.execute("SET a hello") == "OK"
    assert interp.execute("GET a") == "hello"
    assert interp.execute("get a") == "hello"
    assert interp.execute("GET A") == "NULL"
    assert interp.execute("DEL a") == "1"
    assert interp.execute("DEL a") == "0"
    assert interp.execute("   ") == ""


def test_interp_count_keys(interp):
    interp.execute("SET b v")
    interp.execute("SET a v")
    interp.execute("SET c w")
    assert interp.execute("COUNT v") == "2"
    assert interp.execute("KEYS") == "a b c"
    assert interp.execute("KEYS b") == "b"
    assert interp.execute("KEYS zz") == "(empty)"


def test_interp_ttl(interp, clock):
    assert interp.execute("SET s v EX 2.5") == "OK"
    assert interp.execute("TTL s") == "2.500"
    assert interp.execute("SET n v") == "OK"
    assert interp.execute("TTL n") == "none"
    assert interp.execute("TTL zz") == "-1"
    clock.advance(3)
    assert interp.execute("GET s") == "NULL"


def test_interp_transactions(interp):
    assert interp.execute("ROLLBACK") == "ERR no transaction"
    assert interp.execute("COMMIT") == "ERR no transaction"
    interp.execute("SET a 1")
    assert interp.execute("BEGIN") == "OK"
    interp.execute("SET a 2")
    assert interp.execute("BEGIN") == "OK"
    interp.execute("DEL a")
    assert interp.execute("GET a") == "NULL"
    assert interp.execute("ROLLBACK") == "OK"
    assert interp.execute("GET a") == "2"
    assert interp.execute("COMMIT") == "OK"
    assert interp.execute("ROLLBACK") == "ERR no transaction"
    assert interp.store.get("a") == "2"


def test_interp_errors_do_not_change_state(interp):
    for line in ["SET a", "SET a 1 EX", "SET a 1 EX -3", "SET a 1 EX abc", "SET a 1 PX 5", "GET",
                 "GET a b", "FLY away", "BEGIN now", "KEYS a b", "TTL"]:
        r = interp.execute(line)
        assert r.startswith("ERR "), (line, r)
    assert interp.store.keys() == []


def test_interp_default_store():
    i = Interpreter()
    assert isinstance(i.store, Store)
    assert i.execute("SET k v") == "OK"
    assert i.store.get("k") == "v"
