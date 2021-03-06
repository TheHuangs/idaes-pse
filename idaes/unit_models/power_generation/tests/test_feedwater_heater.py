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

import pytest
import pyomo.environ as pyo
from idaes.core import FlowsheetBlock
from idaes.unit_models.heat_exchanger import (delta_temperature_underwood2_rule,
    delta_temperature_underwood_rule, delta_temperature_lmtd_rule)
from idaes.property_models import Iapws95ParameterBlock
from idaes.unit_models.power_generation import FWH0D
from idaes.ui.report import degrees_of_freedom
from idaes.property_models.iapws95 import iapws95_available

prop_available = iapws95_available()

# See if ipopt is available and set up solver
if pyo.SolverFactory('ipopt').available():
    solver = pyo.SolverFactory('ipopt')
else:
    solver = None

@pytest.mark.skipif(not prop_available, reason="IAPWS not available")
@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_fwh_model():
    model = pyo.ConcreteModel()
    model.fs = FlowsheetBlock(default={
        "dynamic": False,
        "default_property_package": Iapws95ParameterBlock()})
    model.fs.properties = model.fs.config.default_property_package
    model.fs.fwh = FWH0D(default={
        "has_desuperheat":True,
        "has_drain_cooling":True,
        "has_drain_mixer":True,
        "property_package":model.fs.properties})

    model.fs.fwh.desuperheat.inlet_1.flow_mol.fix(100)
    model.fs.fwh.desuperheat.inlet_1.flow_mol.unfix()
    model.fs.fwh.desuperheat.inlet_1.pressure.fix(201325)
    model.fs.fwh.desuperheat.inlet_1.enth_mol.fix(60000)
    model.fs.fwh.drain_mix.drain.flow_mol.fix(1)
    model.fs.fwh.drain_mix.drain.pressure.fix(201325)
    model.fs.fwh.drain_mix.drain.enth_mol.fix(20000)
    model.fs.fwh.cooling.inlet_2.flow_mol.fix(400)
    model.fs.fwh.cooling.inlet_2.pressure.fix(101325)
    model.fs.fwh.cooling.inlet_2.enth_mol.fix(3000)
    model.fs.fwh.condense.area.fix(1000)
    model.fs.fwh.condense.overall_heat_transfer_coefficient.fix(100)
    model.fs.fwh.desuperheat.area.fix(1000)
    model.fs.fwh.desuperheat.overall_heat_transfer_coefficient.fix(10)
    model.fs.fwh.cooling.area.fix(1000)
    model.fs.fwh.cooling.overall_heat_transfer_coefficient.fix(10)
    model.fs.fwh.initialize(optarg={"max_iter":50})

    assert(degrees_of_freedom(model) == 0)
    assert(abs(pyo.value(model.fs.fwh.desuperheat.inlet_1.flow_mol[0]) - 98.335) < 0.01)
