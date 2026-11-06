class Tally:
    def __init__(self):
        self.count = 0
        self.total = 0
        self.minimum = None
        self.maximum = None
        self._values = []

    def observe(self, x):
        self.count += 1
        self.total += x
        self._values.append(x)
        self.minimum = x if self.minimum is None else min(self.minimum, x)
        self.maximum = x if self.maximum is None else max(self.maximum, x)

    def mean(self):
        return None if self.count == 0 else self.total / self.count

    def variance(self):
        if self.count < 2:
            return None
        m = self.total / self.count
        return sum((v - m) ** 2 for v in self._values) / (self.count - 1)


class TimeSeries:
    def __init__(self, env, initial=0):
        self.env = env
        self.start = env.now
        self._points = [(env.now, initial)]

    @property
    def level(self):
        return self._points[-1][1]

    def update(self, value):
        t = self.env.now
        if self._points[-1][0] == t:
            self._points[-1] = (t, value)
        else:
            self._points.append((t, value))

    def mean(self, until=None):
        end = self.env.now if until is None else until
        if end < self.start or end > self.env.now:
            raise ValueError("until outside the recorded window")
        if end == self.start:
            return float(self._points[0][1])
        area = 0.0
        for i, (t, v) in enumerate(self._points):
            if t >= end:
                break
            t_next = self._points[i + 1][0] if i + 1 < len(self._points) else end
            area += v * (min(t_next, end) - t)
        return area / (end - self.start)
