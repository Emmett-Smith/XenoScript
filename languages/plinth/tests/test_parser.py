import pytest

import parser as P
from lexer import PlinthError


def test_minimal_scenario_parses():
    src = """
    define scenario tiny
      set duration = 10s
      set step = 1s
    end_scenario
    """
    program = P.parse_source(src)
    assert len(program.toplevels) == 1
    assert isinstance(program.toplevels[0], P.ScenarioDef)
    assert program.toplevels[0].name == "tiny"


def test_platform_with_position_and_bind():
    src = """
    define platform uav_01 type air
      position at 1.00deg 2.00deg
      bind primary_sensor <- radar_b
    end_platform
    """
    program = P.parse_source(src)
    plat = program.toplevels[0]
    assert isinstance(plat, P.PlatformDef)
    assert plat.plat_type == "air"
    assert isinstance(plat.stmts[0], P.PositionStmt)
    assert isinstance(plat.stmts[1], P.BindStmt)
    assert plat.stmts[1].name == "primary_sensor"
    assert plat.stmts[1].target == "radar_b"


def test_execute_at_and_actions():
    src = """
    execute
      at 5s spawn uav_01 on route r1
      at 6s activate radar_a
      at 7s trace "hi"
      at 8s halt
    end_execute
    """
    program = P.parse_source(src)
    ex = program.toplevels[0]
    assert isinstance(ex, P.ExecuteBlock)
    assert isinstance(ex.stmts[0].action, P.SpawnAction)
    assert ex.stmts[0].action.route == "r1"
    assert isinstance(ex.stmts[1].action, P.ActivateAction)
    assert isinstance(ex.stmts[2].action, P.TraceAction)
    assert isinstance(ex.stmts[3].action, P.HaltAction)


def test_every_for_parses():
    src = """
    execute
      every 5s for 20s report radar_a
    end_execute
    """
    program = P.parse_source(src)
    stmt = program.toplevels[0].stmts[0]
    assert isinstance(stmt, P.ExecEvery)
    assert stmt.period == (5.0, "s")
    assert stmt.for_window == (20.0, "s")


def test_route_with_waypoints():
    src = """
    define route r1
      waypoint
        position at 1.00deg 1.00deg
      end_waypoint
      waypoint
        position at 2.00deg 2.00deg
      end_waypoint
    end_route
    """
    program = P.parse_source(src)
    route = program.toplevels[0]
    assert isinstance(route, P.RouteDef)
    assert len(route.waypoints) == 2


def test_mismatched_terminator_is_e004():
    src = """
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_sensor
    """
    with pytest.raises(PlinthError) as exc:
        P.parse_source(src)
    assert exc.value.code == "E004"


def test_unterminated_block_is_e002():
    src = """
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    """
    with pytest.raises(PlinthError) as exc:
        P.parse_source(src)
    assert exc.value.code == "E002"


def test_inherit_parses():
    src = """
    define platform uav_02 type air
      inherit from uav_01
    end_platform
    """
    program = P.parse_source(src)
    stmt = program.toplevels[0].stmts[0]
    assert isinstance(stmt, P.InheritStmt)
    assert stmt.target == "uav_01"
