def split_lines(text):
    out, start = [], 0
    while True:
        i = text.find("\n", start)
        if i < 0:
            break
        out.append(text[start:i + 1])
        start = i + 1
    if start < len(text):
        out.append(text[start:])
    return out


def diff_lines(a, b):
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, nxt, ai = L[i], L[i + 1], a[i]
        for j in range(m - 1, -1, -1):
            if ai == b[j]:
                row[j] = nxt[j + 1] + 1
            else:
                row[j] = max(nxt[j], row[j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            out.append((" ", a[i]))
            i += 1
            j += 1
        elif L[i + 1][j] >= L[i][j + 1]:
            out.append(("-", a[i]))
            i += 1
        else:
            out.append(("+", b[j]))
            j += 1
    out.extend(("-", x) for x in a[i:])
    out.extend(("+", x) for x in b[j:])
    return out
