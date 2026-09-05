"""PLINTH recursive-descent parser. Tokens -> AST.

Grammar per 01_LANGUAGE.md Sec 4. Structural/lexical errors are raised as
a single PlinthError as soon as found (first-error-wins strategy -- see
the language agent's final report for why: it keeps this implementation
inside the ~500-line target while still hitting every error code with a
dedicated, deterministic fixture).
"""
from dataclasses import dataclass, field
from typing import Optional

from lexer import tokenize, PlinthError, Token
from grammar import PLAT_TYPES, SENS_TYPES


# ---------------------------------------------------------------- AST ----
@dataclass
class SetStmt:
    attr: str
    value_kind: str  # quantity | number | string | bool | ident
    value: object
    line: int
    col: int


@dataclass
class BindStmt:
    name: str
    target: str
    line: int
    col: int


@dataclass
class InheritStmt:
    target: str
    line: int
    col: int


@dataclass
class PositionStmt:
    lat: tuple
    lon: tuple
    line: int
    col: int


@dataclass
class SpawnAction:
    platform: str
    route: Optional[str]
    line: int
    col: int


@dataclass
class ActivateAction:
    ident: str
    line: int
    col: int


@dataclass
class DeactivateAction:
    ident: str
    line: int
    col: int


@dataclass
class ReportAction:
    ident: str
    line: int
    col: int


@dataclass
class TraceAction:
    text: str
    line: int
    col: int


@dataclass
class HaltAction:
    line: int
    col: int


@dataclass
class ExecAt:
    time: tuple
    action: object
    line: int
    col: int


@dataclass
class ExecEvery:
    period: tuple
    for_window: Optional[tuple]
    action: object
    line: int
    col: int


@dataclass
class Waypoint:
    stmts: list
    line: int
    col: int


@dataclass
class ScenarioDef:
    name: str
    stmts: list
    line: int
    col: int


@dataclass
class PlatformDef:
    name: str
    plat_type: str
    stmts: list
    line: int
    col: int


@dataclass
class SensorDef:
    name: str
    sens_type: str
    stmts: list
    line: int
    col: int


@dataclass
class RouteDef:
    name: str
    waypoints: list
    line: int
    col: int


@dataclass
class SignalDef:
    name: str
    stmts: list
    line: int
    col: int


@dataclass
class ExecuteBlock:
    stmts: list
    line: int
    col: int


@dataclass
class Program:
    toplevels: list = field(default_factory=list)


END_KEYWORDS = {
    "end_scenario", "end_platform", "end_sensor", "end_route",
    "end_signal", "end_waypoint", "end_execute",
}


class Parser:
    def __init__(self, tokens, filename):
        self.tokens = tokens
        self.pos = 0
        self.filename = filename

    # -- low level -------------------------------------------------
    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def at_keyword(self, *names):
        tok = self.peek()
        return tok.kind == "KEYWORD" and tok.value in names

    def expect_keyword(self, name):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == name:
            return self.advance()
        raise PlinthError("E001", tok.line, tok.col,
                           f"expected '{name}', got {self._describe(tok)}")

    def expect_ident(self):
        tok = self.peek()
        if tok.kind == "IDENT":
            return self.advance()
        raise PlinthError("E001", tok.line, tok.col,
                           f"expected identifier, got {self._describe(tok)}")

    def expect_kind(self, kind, what):
        tok = self.peek()
        if tok.kind == kind:
            return self.advance()
        raise PlinthError("E001", tok.line, tok.col,
                           f"expected {what}, got {self._describe(tok)}")

    @staticmethod
    def _describe(tok):
        if tok.kind == "EOF":
            return "end of file"
        if tok.kind == "KEYWORD":
            return f"keyword '{tok.value}'"
        if tok.kind == "IDENT":
            return f"identifier '{tok.value}'"
        if tok.kind == "QUANTITY":
            return f"quantity {tok.value[0]}{tok.value[1]}"
        if tok.kind == "STRING":
            return f'string "{tok.value}"'
        return f"{tok.kind} {tok.value!r}"

    # -- program -----------------------------------------------------
    def parse_program(self):
        toplevels = []
        while self.peek().kind != "EOF":
            tok = self.peek()
            if tok.kind == "KEYWORD" and tok.value == "define":
                toplevels.append(self.parse_define())
            elif tok.kind == "KEYWORD" and tok.value == "execute":
                toplevels.append(self.parse_execute())
            else:
                raise PlinthError("E001", tok.line, tok.col,
                                   f"unexpected {self._describe(tok)} at top level")
        return Program(toplevels)

    def parse_define(self):
        self.expect_keyword("define")
        tok = self.peek()
        if not (tok.kind == "KEYWORD" and tok.value in
                ("scenario", "platform", "sensor", "route", "signal")):
            raise PlinthError("E003", tok.line, tok.col,
                               f"unknown keyword {self._describe(tok)} after 'define'; "
                               f"expected one of scenario, platform, sensor, route, signal")
        kind = tok.value
        if kind == "scenario":
            return self.parse_scenario()
        if kind == "platform":
            return self.parse_platform()
        if kind == "sensor":
            return self.parse_sensor()
        if kind == "route":
            return self.parse_route()
        return self.parse_signal()

    # -- block body helper --------------------------------------------
    def parse_block_body(self, stmt_parser, end_keyword, block_desc, open_line):
        stmts = []
        while True:
            tok = self.peek()
            if tok.kind == "EOF":
                raise PlinthError("E002", open_line, 1,
                                   f"unterminated {block_desc}: missing '{end_keyword}' "
                                   f"(opened at line {open_line})")
            if tok.kind == "KEYWORD" and tok.value == end_keyword:
                self.advance()
                break
            if tok.kind == "KEYWORD" and tok.value in END_KEYWORDS:
                raise PlinthError("E004", tok.line, tok.col,
                                   f"mismatched terminator: expected '{end_keyword}' "
                                   f"to close {block_desc} opened at line {open_line}, "
                                   f"got '{tok.value}'")
            stmts.append(stmt_parser())
        return stmts

    # -- scenario -------------------------------------------------------
    def parse_scenario(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("scenario")
        name = self.expect_ident().value
        stmts = self.parse_block_body(self.parse_scenario_stmt, "end_scenario",
                                       f"scenario '{name}'", line)
        return ScenarioDef(name, stmts, line, col)

    def parse_scenario_stmt(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "set":
            return self.parse_set_stmt()
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)} inside scenario")

    # -- platform ---------------------------------------------------------
    def parse_platform(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("platform")
        name = self.expect_ident().value
        self.expect_keyword("type")
        tok = self.peek()
        if not (tok.kind == "IDENT" and tok.value in PLAT_TYPES) and not \
                (tok.kind == "KEYWORD" and tok.value in PLAT_TYPES):
            raise PlinthError("E003", tok.line, tok.col,
                               f"unknown platform type {self._describe(tok)}; "
                               f"expected one of {', '.join(PLAT_TYPES)}")
        plat_type = tok.value
        self.advance()
        stmts = self.parse_block_body(self.parse_platform_stmt, "end_platform",
                                       f"platform '{name}'", line)
        return PlatformDef(name, plat_type, stmts, line, col)

    def parse_platform_stmt(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "set":
            return self.parse_set_stmt()
        if tok.kind == "KEYWORD" and tok.value == "bind":
            return self.parse_bind_stmt()
        if tok.kind == "KEYWORD" and tok.value == "inherit":
            return self.parse_inherit_stmt()
        if tok.kind == "KEYWORD" and tok.value == "position":
            return self.parse_position_stmt()
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)} inside platform")

    # -- sensor -------------------------------------------------------------
    def parse_sensor(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("sensor")
        name = self.expect_ident().value
        self.expect_keyword("type")
        tok = self.peek()
        if not (tok.kind == "IDENT" and tok.value in SENS_TYPES):
            raise PlinthError("E003", tok.line, tok.col,
                               f"unknown sensor type {self._describe(tok)}; "
                               f"expected one of {', '.join(SENS_TYPES)}")
        sens_type = tok.value
        self.advance()
        stmts = self.parse_block_body(self.parse_sensor_stmt, "end_sensor",
                                       f"sensor '{name}'", line)
        return SensorDef(name, sens_type, stmts, line, col)

    def parse_sensor_stmt(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "set":
            return self.parse_set_stmt()
        if tok.kind == "KEYWORD" and tok.value == "bind":
            return self.parse_bind_stmt()
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)} inside sensor")

    # -- route / waypoint -----------------------------------------------
    def parse_route(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("route")
        name = self.expect_ident().value
        waypoints = []
        while True:
            tok = self.peek()
            if tok.kind == "EOF":
                raise PlinthError("E002", line, 1,
                                   f"unterminated route '{name}': missing 'end_route' "
                                   f"(opened at line {line})")
            if tok.kind == "KEYWORD" and tok.value == "end_route":
                self.advance()
                break
            if tok.kind == "KEYWORD" and tok.value in END_KEYWORDS:
                raise PlinthError("E004", tok.line, tok.col,
                                   f"mismatched terminator: expected 'end_route' "
                                   f"to close route '{name}' opened at line {line}, "
                                   f"got '{tok.value}'")
            if tok.kind == "KEYWORD" and tok.value == "waypoint":
                waypoints.append(self.parse_waypoint())
                continue
            raise PlinthError("E001", tok.line, tok.col,
                               f"unexpected {self._describe(tok)} inside route "
                               f"(expected 'waypoint' or 'end_route')")
        return RouteDef(name, waypoints, line, col)

    def parse_waypoint(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("waypoint")
        stmts = self.parse_block_body(self.parse_waypoint_stmt, "end_waypoint",
                                       "waypoint", line)
        return Waypoint(stmts, line, col)

    def parse_waypoint_stmt(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "position":
            return self.parse_position_stmt()
        if tok.kind == "KEYWORD" and tok.value == "set":
            return self.parse_set_stmt()
        if tok.kind == "KEYWORD" and tok.value == "at":
            # Gotcha 01_LANGUAGE.md Sec 5.2: temporal 'at' used where spatial
            # is expected. Parse the temporal shape so the input is fully
            # consumed, then reject it with a context-specific message.
            at_tok = self.advance()
            self.expect_kind("QUANTITY", "a time quantity")
            self.parse_action()
            raise PlinthError("E031", at_tok.line, at_tok.col,
                               "temporal 'at <time> <action>' used inside waypoint; "
                               "waypoints use spatial 'position at <lat> <lon>' instead")
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)} inside waypoint")

    # -- signal --------------------------------------------------------
    def parse_signal(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("signal")
        name = self.expect_ident().value
        stmts = self.parse_block_body(self.parse_signal_stmt, "end_signal",
                                       f"signal '{name}'", line)
        return SignalDef(name, stmts, line, col)

    def parse_signal_stmt(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "set":
            return self.parse_set_stmt()
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)} inside signal")

    # -- execute -------------------------------------------------------
    def parse_execute(self):
        line, col = self.peek().line, self.peek().col
        self.expect_keyword("execute")
        stmts = self.parse_block_body(self.parse_exec_stmt, "end_execute",
                                       "execute block", line)
        return ExecuteBlock(stmts, line, col)

    def parse_exec_stmt(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "at":
            at_tok = self.advance()
            time_q = self.expect_kind("QUANTITY", "a time quantity").value
            action = self.parse_action()
            return ExecAt(time_q, action, at_tok.line, at_tok.col)
        if tok.kind == "KEYWORD" and tok.value == "every":
            ev_tok = self.advance()
            period = self.expect_kind("QUANTITY", "a time quantity").value
            for_window = None
            if self.at_keyword("for"):
                self.advance()
                for_window = self.expect_kind("QUANTITY", "a time quantity").value
            action = self.parse_action()
            return ExecEvery(period, for_window, action, ev_tok.line, ev_tok.col)
        if tok.kind == "KEYWORD" and tok.value == "position":
            # Gotcha 01_LANGUAGE.md Sec 5.2: spatial 'at' used inside execute.
            pos_tok = self.advance()
            self.expect_keyword("at")
            self.expect_kind("QUANTITY", "a latitude quantity")
            self.expect_kind("QUANTITY", "a longitude quantity")
            raise PlinthError("E030", pos_tok.line, pos_tok.col,
                               "spatial 'position at <lat> <lon>' used inside execute; "
                               "execute only takes temporal 'at <time> <action>'")
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)} inside execute "
                           f"(expected 'at' or 'every')")

    def parse_action(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "spawn":
            self.advance()
            plat = self.expect_ident().value
            route = None
            if self.at_keyword("on"):
                self.advance()
                self.expect_keyword("route")
                route = self.expect_ident().value
            return SpawnAction(plat, route, tok.line, tok.col)
        if tok.kind == "KEYWORD" and tok.value == "activate":
            self.advance()
            ident = self.expect_ident().value
            return ActivateAction(ident, tok.line, tok.col)
        if tok.kind == "KEYWORD" and tok.value == "deactivate":
            self.advance()
            ident = self.expect_ident().value
            return DeactivateAction(ident, tok.line, tok.col)
        if tok.kind == "KEYWORD" and tok.value == "report":
            self.advance()
            ident = self.expect_ident().value
            return ReportAction(ident, tok.line, tok.col)
        if tok.kind == "KEYWORD" and tok.value == "trace":
            self.advance()
            s = self.expect_kind("STRING", "a string literal").value
            return TraceAction(s, tok.line, tok.col)
        if tok.kind == "KEYWORD" and tok.value == "halt":
            self.advance()
            return HaltAction(tok.line, tok.col)
        raise PlinthError("E001", tok.line, tok.col,
                           f"unexpected {self._describe(tok)}; expected an action "
                           f"(spawn, activate, deactivate, report, trace, halt)")

    # -- shared statement forms -----------------------------------------
    def parse_set_stmt(self):
        set_tok = self.advance()  # 'set'
        attr_tok = self.peek()
        if attr_tok.kind not in ("KEYWORD", "IDENT"):
            raise PlinthError("E001", attr_tok.line, attr_tok.col,
                               f"expected an attribute name, got {self._describe(attr_tok)}")
        attr = attr_tok.value
        self.advance()
        self.expect_kind("EQUALS", "'='")
        val_tok = self.peek()
        if val_tok.kind == "QUANTITY":
            self.advance()
            return SetStmt(attr, "quantity", val_tok.value, set_tok.line, set_tok.col)
        if val_tok.kind == "NUMBER":
            self.advance()
            return SetStmt(attr, "number", val_tok.value, set_tok.line, set_tok.col)
        if val_tok.kind == "STRING":
            self.advance()
            return SetStmt(attr, "string", val_tok.value, set_tok.line, set_tok.col)
        if val_tok.kind == "BOOL":
            self.advance()
            return SetStmt(attr, "bool", val_tok.value, set_tok.line, set_tok.col)
        if val_tok.kind == "IDENT":
            self.advance()
            return SetStmt(attr, "ident", val_tok.value, set_tok.line, set_tok.col)
        raise PlinthError("E001", val_tok.line, val_tok.col,
                           f"expected a value after '=', got {self._describe(val_tok)}")

    def parse_bind_stmt(self):
        bind_tok = self.advance()  # 'bind'
        name_tok = self.peek()
        if name_tok.kind not in ("KEYWORD", "IDENT"):
            raise PlinthError("E001", name_tok.line, name_tok.col,
                               f"expected a bind target name, got {self._describe(name_tok)}")
        name = name_tok.value
        self.advance()
        self.expect_kind("ARROW", "'<-'")
        rhs_tok = self.peek()
        if rhs_tok.kind != "IDENT":
            raise PlinthError("E021", bind_tok.line, bind_tok.col,
                               f"bind target must be an identifier, got "
                               f"{self._describe(rhs_tok)}; write 'bind {name} <- <identifier>'")
        self.advance()
        return BindStmt(name, rhs_tok.value, bind_tok.line, bind_tok.col)

    def parse_inherit_stmt(self):
        inh_tok = self.advance()  # 'inherit'
        self.expect_keyword("from")
        target = self.expect_ident().value
        return InheritStmt(target, inh_tok.line, inh_tok.col)

    def parse_position_stmt(self):
        pos_tok = self.advance()  # 'position'
        self.expect_keyword("at")
        lat = self.expect_kind("QUANTITY", "a latitude quantity").value
        lon = self.expect_kind("QUANTITY", "a longitude quantity").value
        return PositionStmt(lat, lon, pos_tok.line, pos_tok.col)


def parse_source(source, filename="candidate.plth"):
    tokens = tokenize(source)
    parser = Parser(tokens, filename)
    return parser.parse_program()
