##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2019, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################
"""
Tests for turbine multistage model.

Author: John Eslick
"""
import pytest

from pyomo.environ import (ConcreteModel, SolverFactory, TransformationFactory,
                           Constraint, value)
from pyomo.network import Arc

from idaes.core import FlowsheetBlock
from idaes.unit_models import Heater
from idaes.unit_models.power_generation import (
    TurbineMultistage, TurbineStage, TurbineInletStage, TurbineOutletStage)
from idaes.property_models import iapws95_ph
from idaes.property_models.iapws95 import iapws95_available
from idaes.ui.report import degrees_of_freedom, active_equalities

prop_available = iapws95_available()

# See if ipopt is available and set up solver
if SolverFactory('ipopt').available():
    solver = SolverFactory('ipopt')
    solver.options = {'tol': 1e-6}
else:
    solver = None

def build_turbine_for_run_test():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.properties = iapws95_ph.Iapws95ParameterBlock()
    # roughly based on NETL baseline studies
    m.fs.turb = TurbineMultistage(default={
        "property_package": m.fs.properties,
        "num_hp": 7,
        "num_ip": 14,
        "num_lp": 11,
        "hp_split_locations": [4,7],
        "ip_split_locations": [5, 14],
        "lp_split_locations": [4,7,9,11],
        "hp_disconnect": [7],
        "ip_split_num_outlets": {14:3}})

    # Add reheater
    m.fs.reheat = Heater(default={"property_package": m.fs.properties})
    m.fs.hp_to_reheat = Arc(source=m.fs.turb.hp_split[7].outlet_1,
                            destination=m.fs.reheat.inlet)
    m.fs.reheat_to_ip = Arc(source=m.fs.reheat.outlet,
                            destination=m.fs.turb.ip_stages[1].inlet)

    return m

@pytest.mark.skipif(not prop_available, reason="IAPWS not available")
@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_initialize():
    """Make a turbine model and make sure it doesn't throw exception"""
    m = build_turbine_for_run_test()
    turb = m.fs.turb

    # Set the inlet of the turbine
    p = 2.4233e7
    hin = iapws95_ph.htpx(T=880, P=p)
    m.fs.turb.inlet_split.inlet.enth_mol[0].fix(hin)
    m.fs.turb.inlet_split.inlet.flow_mol[0].fix(26000)
    m.fs.turb.inlet_split.inlet.pressure[0].fix(p)

    # Set the inlet of the ip section, which is disconnected
    # here to insert reheater
    p = 7.802e+06
    hin = iapws95_ph.htpx(T=880, P=p)
    m.fs.turb.ip_stages[1].inlet.enth_mol[0].value = hin
    m.fs.turb.ip_stages[1].inlet.flow_mol[0].value = 25220.0
    m.fs.turb.ip_stages[1].inlet.pressure[0].value = p

    for i, s in turb.hp_stages.items():
        s.ratioP[:] = 0.88
        s.efficiency_isentropic[:] = 0.9
    for i, s in turb.ip_stages.items():
        s.ratioP[:] = 0.85
        s.efficiency_isentropic[:] = 0.9
    for i, s in turb.lp_stages.items():
        s.ratioP[:] = 0.82
        s.efficiency_isentropic[:] = 0.9

    turb.hp_split[4].split_fraction[0,"outlet_2"].fix(0.03)
    turb.hp_split[7].split_fraction[0,"outlet_2"].fix(0.03)
    turb.ip_split[5].split_fraction[0,"outlet_2"].fix(0.04)
    turb.ip_split[14].split_fraction[0,"outlet_2"].fix(0.04)
    turb.ip_split[14].split_fraction[0,"outlet_3"].fix(0.15)
    turb.lp_split[4].split_fraction[0,"outlet_2"].fix(0.04)
    turb.lp_split[7].split_fraction[0,"outlet_2"].fix(0.04)
    turb.lp_split[9].split_fraction[0,"outlet_2"].fix(0.04)
    turb.lp_split[11].split_fraction[0,"outlet_2"].fix(0.04)

    # Congiure with reheater for a full test
    turb.ip_stages[1].inlet.unfix()
    turb.inlet_split.inlet.flow_mol.unfix()
    turb.inlet_mix.use_equal_pressure_constraint()
    turb.initialize(outlvl=1)

    for t in m.fs.time:
        m.fs.reheat.inlet.flow_mol[t].value = \
            value(turb.hp_split[7].outlet_1_state[t].flow_mol)
        m.fs.reheat.inlet.enth_mol[t].value = \
            value(turb.hp_split[7].outlet_1_state[t].enth_mol)
        m.fs.reheat.inlet.pressure[t].value = \
            value(turb.hp_split[7].outlet_1_state[t].pressure)
    m.fs.reheat.initialize(outlvl=4)
    def reheat_T_rule(b, t):
        return m.fs.reheat.control_volume.properties_out[t].temperature == 880
    m.fs.reheat.temperature_out_equation = Constraint(
            m.fs.reheat.flowsheet().config.time,
            rule=reheat_T_rule)

    TransformationFactory("network.expand_arcs").apply_to(m)
    m.fs.turb.outlet_stage.control_volume.properties_out[0].pressure.fix()

    assert(degrees_of_freedom(m)==0)
    solver.solve(m, tee=True)
    for c in active_equalities(m):
        assert(abs(c.body() - c.lower) < 1e-4)

    return m
