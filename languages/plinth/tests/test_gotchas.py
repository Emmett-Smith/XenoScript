"""The four deliberate gotchas from 01_LANGUAGE.md Sec 5, at least three
cases each (spec requirement)."""
import pytest

import parser as P
import checker as C
import runtime as R
from lexer import PlinthError, tokenize


def parse_and_check(src):
    program = P.parse_source(src)
    return C.check_program(program)


def expect_code(src, code):
    with pytest.raises(PlinthError) as exc:
        parse_and_check(src)
    assert exc.value.code == code, f"expected {code}, got {exc.value.code}: {exc.value.message}"


# ---------------------------------------------------------------- 5.1 ----
# set vs bind: assignment vs deferred reference.

def test_gotcha_5_1_case1_bind_wrong_target_shape():
    expect_code("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      bind x <- 5m
    end_platform
    """, "E021")


def test_gotcha_5_1_case2_set_used_on_reference():
    expect_code("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set primary_sensor = radar_b
    end_platform
    """, "E022")


def test_gotcha_5_1_case3_unresolved_bind():
    expect_code("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      bind primary_sensor <- ghost
    end_platform
    """, "E020")


def test_gotcha_5_1_case4_forward_bind_is_legal():
    # the whole point: bind MAY point forward, unlike ordinary references.
    world = parse_and_check("""
    define platform uav_02 type air
      position at 1.00deg 1.00deg
      bind primary_sensor <- radar_b
    end_platform

    define sensor radar_b type radar
      bind mount <- uav_02
      set range_max = 1000m
    end_sensor
    """)
    assert world.platforms["uav_02"]["refs"]["primary_sensor"] == "radar_b"


# ---------------------------------------------------------------- 5.2 ----
# `at` is context-sensitive: spatial in waypoint, temporal in execute.

def test_gotcha_5_2_case1_spatial_at_inside_execute():
    expect_code("""
    define scenario s1
      set duration = 10s
      set step = 1s
    end_scenario
    execute
      position at 1.00deg 1.00deg
    end_execute
    """, "E030")


def test_gotcha_5_2_case2_temporal_at_inside_waypoint():
    expect_code("""
    define route r1
      waypoint
        at 30s activate radar_a
      end_waypoint
    end_route
    """, "E031")


def test_gotcha_5_2_case3_spatial_at_in_waypoint_is_legal():
    program = P.parse_source("""
    define route r1
      waypoint
        position at 1.00deg 1.00deg
      end_waypoint
    end_route
    """)
    world = C.check_program(program)
    assert world.routes["r1"][0]["position"] is not None


def test_gotcha_5_2_case4_temporal_at_in_execute_is_legal():
    world = parse_and_check("""
    define scenario s1
      set duration = 10s
      set step = 1s
    end_scenario
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform
    execute
      at 5s spawn uav_01
    end_execute
    """)
    assert "uav_01" in world.platforms


# ---------------------------------------------------------------- 5.3 ----
# angle_mode must match every angle literal in the whole file.

def test_gotcha_5_3_case1_default_deg_rejects_rad():
    expect_code("""
    define platform uav_01 type air
      position at 1.00deg 1.00rad
    end_platform
    """, "E042")


def test_gotcha_5_3_case2_explicit_rad_rejects_deg():
    expect_code("""
    define scenario s1
      set duration = 10s
      set step = 1s
      set angle_mode = rad
    end_scenario
    define platform uav_01 type air
      position at 1.00deg 1.00rad
    end_platform
    """, "E042")


def test_gotcha_5_3_case3_conflict_on_a_second_attribute_not_just_position():
    expect_code("""
    define scenario s1
      set duration = 10s
      set step = 1s
      set angle_mode = rad
    end_scenario
    define platform uav_01 type air
      position at 1.00rad 1.00rad
      set heading = 90deg
    end_platform
    """, "E042")


def test_gotcha_5_3_case4_consistent_rad_is_legal():
    world = parse_and_check("""
    define scenario s1
      set duration = 10s
      set step = 1s
      set angle_mode = rad
    end_scenario
    define platform uav_01 type air
      position at 0.50rad 0.50rad
      set heading = 1.00rad
    end_platform
    """)
    assert world.angle_mode == "rad"


# ---------------------------------------------------------------- 5.4 ----
# no space between number and unit.

def test_gotcha_5_4_case1_space_before_unit_is_e043():
    with pytest.raises(PlinthError) as exc:
        tokenize("1500 m")
    assert exc.value.code == "E043"


def test_gotcha_5_4_case2_space_before_unit_in_full_file():
    with pytest.raises(PlinthError) as exc:
        P.parse_source("""
        define platform uav_01 type air
          position at 1.00deg 1.00deg
          set altitude = 1500 m
        end_platform
        """)
    assert exc.value.code == "E043"


def test_gotcha_5_4_case3_bare_number_where_unit_required_is_e040():
    expect_code("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set altitude = 1500
    end_platform
    """, "E040")


def test_gotcha_5_4_case4_bare_int_exception_attrs_are_legal_with_no_unit():
    world = parse_and_check("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform

    define sensor radar_a type radar
      bind mount <- uav_01
      set range_max = 1000m
      set priority = 3
    end_sensor
    """)
    assert world.sensors["radar_a"]["attrs"]["priority"] == 3.0


def test_gotcha_5_4_case5_glued_quantity_is_legal():
    world = parse_and_check("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set altitude = 1500m
    end_platform
    """)
    assert world.platforms["uav_01"]["attrs"]["altitude"] == 1500.0
