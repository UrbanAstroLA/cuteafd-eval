from .errors import TransactionError
from .store import Store


class Interpreter:
    def __init__(self, store=None):
        self.store = store if store is not None else Store()

    def execute(self, line):
        parts = line.split()
        if not parts:
            return ""
        cmd, args = parts[0].upper(), parts[1:]
        s = self.store
        try:
            if cmd == "SET":
                if len(args) == 2:
                    s.set(args[0], args[1])
                    return "OK"
                if len(args) == 4 and args[2] == "EX":
                    try:
                        sec = float(args[3])
                    except ValueError:
                        return "ERR invalid expire time"
                    if not sec > 0 or sec != sec or sec == float("inf"):
                        return "ERR invalid expire time"
                    s.set(args[0], args[1], ttl=sec)
                    return "OK"
                return "ERR syntax"
            if cmd == "GET" and len(args) == 1:
                v = s.get(args[0])
                return "NULL" if v is None else v
            if cmd == "DEL" and len(args) == 1:
                return "1" if s.delete(args[0]) else "0"
            if cmd == "COUNT" and len(args) == 1:
                return str(s.count(args[0]))
            if cmd == "KEYS" and len(args) <= 1:
                ks = s.keys(args[0] if args else "")
                return " ".join(ks) if ks else "(empty)"
            if cmd == "TTL" and len(args) == 1:
                t = s.ttl(args[0])
                if t == -1:
                    return "-1"
                if t is None:
                    return "none"
                return format(t, ".3f")
            if cmd in ("BEGIN", "ROLLBACK", "COMMIT") and not args:
                if cmd == "BEGIN":
                    s.begin()
                elif cmd == "ROLLBACK":
                    s.rollback()
                else:
                    s.commit()
                return "OK"
        except TransactionError:
            return "ERR no transaction"
        return "ERR unknown command or wrong arguments"
