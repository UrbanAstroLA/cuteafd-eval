from .lcs import diff_lines, split_lines

NO_NL = "\\ No newline at end of file\n"


def _range(s, n):
    if n == 1:
        return str(s + 1)
    if n == 0:
        return f"{s},0"
    return f"{s + 1},{n}"


def unified_diff(old, new, from_name="a", to_name="b", context=3):
    if context < 0:
        raise ValueError("context must be >= 0")
    if old == new:
        return ""
    script = diff_lines(split_lines(old), split_lines(new))
    # positions (old index, new index) before each entry
    pos, oi, ni = [], 0, 0
    for tag, _ in script:
        pos.append((oi, ni))
        if tag != "+":
            oi += 1
        if tag != "-":
            ni += 1
    changes = [k for k, (tag, _) in enumerate(script) if tag != " "]
    groups, cur = [], [changes[0], changes[0]]
    for k in changes[1:]:
        if k - cur[1] - 1 <= 2 * context:
            cur[1] = k
        else:
            groups.append(cur)
            cur = [k, k]
    groups.append(cur)
    out = [f"--- {from_name}\n", f"+++ {to_name}\n"]
    for first, last in groups:
        lo = first
        while lo > 0 and first - lo < context and script[lo - 1][0] == " ":
            lo -= 1
        hi = last
        while hi + 1 < len(script) and hi - last < context and script[hi + 1][0] == " ":
            hi += 1
        entries = script[lo:hi + 1]
        so, sn = pos[lo]
        no = sum(1 for t, _ in entries if t != "+")
        nn = sum(1 for t, _ in entries if t != "-")
        out.append(f"@@ -{_range(so, no)} +{_range(sn, nn)} @@\n")
        for tag, line in entries:
            if line.endswith("\n"):
                out.append(tag + line)
            else:
                out.append(tag + line + "\n" + NO_NL)
    return "".join(out)
