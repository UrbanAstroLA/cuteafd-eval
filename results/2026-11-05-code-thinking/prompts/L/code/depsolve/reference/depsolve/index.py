from .constraint import Constraint
from .version import Version


class Index:
    def __init__(self):
        self._pkgs = {}  # name -> {Version: {dep: Constraint}}

    def add(self, name, version, dependencies=None):
        v = Version.parse(version)
        deps = {}
        for dep, text in sorted((dependencies or {}).items()):
            if dep == name:
                raise ValueError(f"{name} cannot depend on itself")
            deps[dep] = Constraint.parse(text)
        entry = self._pkgs.setdefault(name, {})
        if v in entry:
            raise ValueError(f"{name} {v} already published")
        entry[v] = deps

    def versions(self, name):
        return sorted(self._pkgs.get(name, {}))

    def dependencies(self, name, version):
        v = version if isinstance(version, Version) else Version.parse(version)
        try:
            return dict(self._pkgs[name][v])
        except KeyError:
            raise KeyError((name, str(v))) from None
