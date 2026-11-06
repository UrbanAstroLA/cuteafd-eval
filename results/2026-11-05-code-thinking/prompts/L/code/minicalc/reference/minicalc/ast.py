from dataclasses import dataclass, field


@dataclass
class Num:
    value: object


@dataclass
class Bool:
    value: bool


@dataclass
class Var:
    name: str


@dataclass
class Unary:
    op: str
    operand: object


@dataclass
class Binary:
    op: str
    left: object
    right: object


@dataclass
class Call:
    name: str
    args: list = field(default_factory=list)


@dataclass
class Assign:
    name: str
    value: object


@dataclass
class Program:
    statements: list = field(default_factory=list)
