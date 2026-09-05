import math

import pytest

import parser as P
import checker as C
from lexer import PlinthError


def check(src):
    program = P.parse_source(src)
    return C.check_program(program)


def check_raises(src):
    program = P.parse_source(src)
    with pytest.raises(PlinthError) as exc:
        C.check_program(program)
    return exc.value


def test_full_platform_resolves():
    world = check("""
    define platform uav_01 type air
      position at 1.00deg 2.00deg
      set altitude = 1500m
    end_platform
    """)
    plat = world.platforms["uav_01"]
    assert plat["attrs"]["altitude"] == pytest.approx(1500.0)
    lat, lon = plat["attrs"]["position"]
    assert lat == pytest.approx(math.radians(1.00))
    assert lon == pytest.approx(math.radians(2.00))


def test_inherit_copies_and_overrides():
    world = check("""
    define platform uav_01 type air
      position at 1.00deg 2.00deg
      set altitude = 1500m
    end_platform

    define platform uav_02 type air
      inherit from uav_01
      set altitude = 2200m
    end_platform
    """)
    base = world.platforms["uav_01"]["attrs"]
    child = world.platforms["uav_02"]["attrs"]
    assert child["position"] == base["position"]
    assert child["altitude"] == pytest.approx(2200.0)


def test_duplicate_toplevel_name_is_e010():
    err = check_raises("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform
    define platform uav_01 type ground
      position at 2.00deg 2.00deg
    end_platform
    """)
    assert err.code == "E010"


def test_required_attribute_missing_is_e052():
    err = check_raises("""
    define platform uav_01 type air
      set altitude = 1500m
    end_platform
    """)
    assert err.code == "E052"


def test_unknown_attribute_is_e050():
    err = check_raises("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set wingspan = 12m
    end_platform
    """)
    assert err.code == "E050"


def test_attribute_wrong_block_is_e051():
    err = check_raises("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set frequency = 100mhz
    end_platform
    """)
    assert err.code == "E051"


def test_dimensional_mismatch_is_e041():
    err = check_raises("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set altitude = 5s
    end_platform
    """)
    assert err.code == "E041"


def test_range_check_is_e060():
    err = check_raises("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
      set altitude = 99999m
    end_platform
    """)
    assert err.code == "E060"


def test_mount_via_bind_resolves_platform_reference():
    world = check("""
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform

    define sensor radar_a type radar
      bind mount <- uav_01
      set range_max = 1000m
    end_sensor
    """)
    assert world.sensors["radar_a"]["mount"] == "uav_01"
