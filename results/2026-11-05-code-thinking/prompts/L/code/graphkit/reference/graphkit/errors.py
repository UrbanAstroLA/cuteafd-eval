class GraphError(Exception):
    pass


class NodeNotFound(GraphError, KeyError):
    pass


class CycleError(GraphError):
    def __init__(self, cycle):
        super().__init__(f"cycle: {cycle!r}")
        self.cycle = cycle
