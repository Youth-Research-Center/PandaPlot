import math
from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch, WireElement
from pandaplot.services.circuit_simulation import CircuitSimulator, parse_circuit_value


def test_parse_circuit_value():
    assert math.isclose(parse_circuit_value("10k"), 10000.0)
    assert math.isclose(parse_circuit_value("100n"), 1e-7)
    assert math.isclose(parse_circuit_value("5V"), 5.0)
    assert math.isclose(parse_circuit_value("1.5M"), 1.5e6)
    assert math.isclose(parse_circuit_value("0.5mA"), 0.0005)


def test_dc_simulation_series_resistors():
    sketch = Sketch(name="Series DC Circuit")
    layer = sketch.get_active_layer()

    v1 = CircuitComponentElement(x=0, y=0, component_type="voltage_source", designator="V1", value="5V")
    gnd = CircuitComponentElement(x=20, y=10, component_type="ground")
    r1 = CircuitComponentElement(x=100, y=0, component_type="resistor", designator="R1", value="10")
    r2 = CircuitComponentElement(x=100, y=100, component_type="resistor", designator="R2", value="10")

    w1 = WireElement(waypoints=[(-20, 0), (80, 0)], start_ref=(v1.id, "t1"), end_ref=(r1.id, "t1"))
    w2 = WireElement(waypoints=[(120, 0), (80, 100)], start_ref=(r1.id, "t2"), end_ref=(r2.id, "t1"))
    w3 = WireElement(waypoints=[(120, 100), (20, 0)], start_ref=(r2.id, "t2"), end_ref=(gnd.id, "t1"))
    w4 = WireElement(waypoints=[(20, 0), (20, 0)], start_ref=(v1.id, "t2"), end_ref=(gnd.id, "t1"))

    layer.elements.extend([v1, gnd, r1, r2, w1, w2, w3, w4])

    sim = CircuitSimulator(sketch)
    res = sim.solve_dc()

    assert math.isclose(res.node_voltages[0], 0.0)

    voltages = list(res.node_voltages.values())
    assert 5.0 in [round(v, 3) for v in voltages]
    assert 2.5 in [round(v, 3) for v in voltages]


def test_dc_simulation_parallel_resistors():
    sketch = Sketch(name="Parallel DC Circuit")
    layer = sketch.get_active_layer()

    v1 = CircuitComponentElement(x=0, y=0, component_type="voltage_source", designator="V1", value="5V")
    gnd = CircuitComponentElement(x=20, y=10, component_type="ground")
    r1 = CircuitComponentElement(x=100, y=0, component_type="resistor", designator="R1", value="10")
    r2 = CircuitComponentElement(x=100, y=50, component_type="resistor", designator="R2", value="10")

    w1 = WireElement(waypoints=[(-20, 0), (80, 0)], start_ref=(v1.id, "t1"), end_ref=(r1.id, "t1"))
    w2 = WireElement(waypoints=[(80, 0), (80, 50)], start_ref=(r1.id, "t1"), end_ref=(r2.id, "t1"))
    w3 = WireElement(waypoints=[(120, 0), (20, 0)], start_ref=(r1.id, "t2"), end_ref=(gnd.id, "t1"))
    w4 = WireElement(waypoints=[(120, 50), (20, 0)], start_ref=(r2.id, "t2"), end_ref=(gnd.id, "t1"))
    w5 = WireElement(waypoints=[(20, 0), (20, 0)], start_ref=(v1.id, "t2"), end_ref=(gnd.id, "t1"))

    layer.elements.extend([v1, gnd, r1, r2, w1, w2, w3, w4, w5])

    sim = CircuitSimulator(sketch)
    res = sim.solve_dc()

    voltages = list(res.node_voltages.values())
    assert 5.0 in [round(v, 3) for v in voltages]
    assert 0.0 in [round(v, 3) for v in voltages]


def test_dc_simulation_transformer_circuit():
    sketch = Sketch(name="Transformer DC Circuit")
    layer = sketch.get_active_layer()

    v1 = CircuitComponentElement(x=0, y=0, component_type="voltage_source", designator="V1", value="10V")
    gnd = CircuitComponentElement(x=0, y=100, component_type="ground")
    trans = CircuitComponentElement(x=100, y=50, component_type="transformer", designator="T1", value="1:1")

    w1 = WireElement(waypoints=[(-20, 0), (80, 40)], start_ref=(v1.id, "t1"), end_ref=(trans.id, "t1"))
    w2 = WireElement(waypoints=[(20, 0), (0, 100)], start_ref=(v1.id, "t2"), end_ref=(gnd.id, "t1"))
    w3 = WireElement(waypoints=[(80, 60), (0, 100)], start_ref=(trans.id, "t2"), end_ref=(gnd.id, "t1"))

    layer.elements.extend([v1, gnd, trans, w1, w2, w3])

    sim = CircuitSimulator(sketch)
    res = sim.solve_dc()

    voltages = list(res.node_voltages.values())
    assert 10.0 in [round(v, 1) for v in voltages]
    assert 0.0 in [round(v, 1) for v in voltages]
