class DepError(Exception):
    pass


class ResolutionError(DepError):
    def __init__(self, package, constraints):
        self.package = package
        self.constraints = list(constraints)
        text = ", ".join(f"{c} (from {src})" for c, src in self.constraints)
        super().__init__(f"conflict on {package}: {text}")


class CycleError(DepError):
    def __init__(self, packages):
        self.packages = sorted(packages)
        super().__init__(f"dependency cycle among: {', '.join(self.packages)}")
