import pytest

import parser as P
import checker as C
import runtime as R
from lexer import PlinthError


def run(src):
    program = P.parse_source(src)
    world = C.check_program(program)
    return R.simulate(world)


COASTAL = """
define scenario coastal_watch
  set duration = 60s
  set step = 0.5s
end_scenario

define platform uav_01 type air
  position at 45.20deg -100.10deg
  set altitude = 1500m
end_platform

define sensor radar_a type radar
  bind mount <- uav_01
  set range_max = 80000m
end_sensor

execute
  at 5s spawn uav_01
  at 5s activate radar_a
  at 10s report radar_a
end_execute
"""


def test_trace_matches_architecture_example():
    lines = run(COASTAL)
    assert lines == [
        "[t=0.000] scenario coastal_watch start step=0.500 duration=60.000",
        "[t=5.000] spawn uav_01 pos=45.2000,-100.1000 alt=1500.000",
        "[t=5.000] activate radar_a on uav_01",
        "[t=10.000] report radar_a range_max=80000.000 detections=0",
        "[t=60.000] scenario end status=ok",
    ]


def test_halt_before_duration_is_e070():
    src = """
    define scenario s1
      set duration = 10s
      set step = 1s
    end_scenario
    execute
      at 5s halt
    end_execute
    """
    program = P.parse_source(src)
    world = C.check_program(program)
    with pytest.raises(PlinthError) as exc:
        R.simulate(world)
    assert exc.value.code == "E070"


def test_report_inactive_sensor_is_e071():
    src = """
    define scenario s1
      set duration = 10s
      set step = 1s
    end_scenario
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform
    define sensor radar_a type radar
      bind mount <- uav_01
      set range_max = 1000m
    end_sensor
    execute
      at 1s spawn uav_01
      at 5s report radar_a
    end_execute
    """
    program = P.parse_source(src)
    world = C.check_program(program)
    with pytest.raises(PlinthError) as exc:
        R.simulate(world)
    assert exc.value.code == "E071"


def test_double_spawn_is_e072():
    src = """
    define scenario s1
      set duration = 10s
      set step = 1s
    end_scenario
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform
    execute
      at 1s spawn uav_01
      at 5s spawn uav_01
    end_execute
    """
    program = P.parse_source(src)
    world = C.check_program(program)
    with pytest.raises(PlinthError) as exc:
        R.simulate(world)
    assert exc.value.code == "E072"


def test_every_for_fires_expected_number_of_times():
    src = """
    define scenario s1
      set duration = 30s
      set step = 1s
    end_scenario
    define platform uav_01 type air
      position at 1.00deg 1.00deg
    end_platform
    define sensor radar_a type radar
      bind mount <- uav_01
      set range_max = 1000m
    end_sensor
    execute
      at 1s spawn uav_01
      at 1s activate radar_a
      every 5s for 20s report radar_a
    end_execute
    """
    lines = run(src)
    report_lines = [l for l in lines if l.split("]")[1].strip().startswith("report")]
    # fires at t=5,10,15,20 (four times, within the 20s window)
    assert len(report_lines) == 4


def test_halt_at_exact_duration_is_legal():
    src = """
    define scenario s1
      set duration = 10s
      set step = 1s
    end_scenario
    execute
      at 10s halt
    end_execute
    """
    lines = run(src)
    assert lines[-2] == "[t=10.000] halt"
    assert lines[-1] == "[t=10.000] scenario end status=ok"
