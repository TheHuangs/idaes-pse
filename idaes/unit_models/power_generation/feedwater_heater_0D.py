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
This file contains 0D feedwater heater models. These models are suitable for
steady state calculations. For dynamic modeling 1D models are required. There
are two models included here.

1) FWHCondensing0D: this is a regular 0D heat exchanger model with a constraint
   added to ensure all the steam fed to the feedwater heater is condensed at the
   outlet. At the side_1 outlet the molar enthalpy is equal to the the staurated
   liquid molar enthalpy.
2) FWH0D is a feedwater heater model with three sections and a mixer for
   combining another feedwater heater's drain outlet with steam extracted from
   the turbine.  The drain mixer, desuperheat, and drain cooling sections are
   optional.  Only the condensing section is required.
"""

__author__ = "John Eslick"

import logging
from pyomo.common.config import ConfigValue, In, ConfigBlock
from pyomo.environ import SolverFactory, TransformationFactory, Var, value
from pyomo.opt import TerminationCondition
from pyomo.network import Arc

from idaes.core import declare_process_block_class, UnitModelBlockData
from idaes.unit_models.heat_exchanger import HeatExchangerData
from idaes.unit_models import Mixer, MomentumMixingType, HeatExchanger
from idaes.core.util import from_json, to_json, StoreSpec
from idaes.ui.report import degrees_of_freedom
from idaes.core import useDefault
from idaes.core.util.config import is_physical_parameter_block

_log = logging.getLogger(__name__)

def _define_feedwater_heater_0D_config(config):
    config.declare("has_drain_mixer", ConfigValue(
            default=True,
            domain=In([True, False]),
            description="Add a mixer to the inlet of the condensing section",
            doc="""Add a mixer to the inlet of the condensing section to add
water from the drain of another feedwaterheater to the steam, if True"""))
    config.declare("has_desuperheat", ConfigValue(
            default=True,
            domain=In([True, False]),
            description="Add a mixer desuperheat section to the heat exchanger",
            doc="Add a mixer desuperheat section to the heat exchanger"))
    config.declare("has_drain_cooling", ConfigValue(
            default=True,
            domain=In([True, False]),
            description="Add a section after condensing section cool condensate.",
            doc="Add a section after condensing section to cool condensate."))
    config.declare("property_package", ConfigValue(
        default=useDefault,
        domain=is_physical_parameter_block,
        description="Property package to use for control volume",
        doc="""Property parameter object used to define property calculations,
**default** - useDefault.
**Valid values:** {
**useDefault** - use default package from parent model or flowsheet,
**PropertyParameterObject** - a PropertyParameterBlock object.}"""))
    config.declare("property_package_args", ConfigBlock(
        implicit=True,
        description="Arguments to use for constructing property packages",
        doc="""A ConfigBlock with arguments to be passed to a property block(s)
and used when constructing these,
**default** - None.
**Valid values:** {
see property package for documentation.}"""))
    config.declare("condense", HeatExchangerData.CONFIG())
    config.declare("desuperheat", HeatExchangerData.CONFIG())
    config.declare("cooling", HeatExchangerData.CONFIG())

def _set_port(p1, p2):
    """
    Copy the values from port p2 to port p1.

    Args:
        p1: port to copy values to
        p2: port to compy values from
    """
    for k, v in p1.vars.items():
        if isinstance(v, Var):
            for i in v:
                v[i].value = value(p2.vars[k][i])

def _set_prop_pack(hxcfg, fwhcfg):
    """
    Set the property package and property pacakge args to the values given for
    the overall feedwater heater model if not otherwise specified.

    Args:
        hxcfg: Heat exchanger subblock config block
        fwhcfg: Overall feedwater heater config block
    """
    if hxcfg.side_1.property_package == useDefault:
        hxcfg.side_1.property_package = fwhcfg.property_package
        hxcfg.side_1.property_package_args = fwhcfg.property_package_args
    if hxcfg.side_2.property_package == useDefault:
        hxcfg.side_2.property_package = fwhcfg.property_package
        hxcfg.side_2.property_package_args = fwhcfg.property_package_args


@declare_process_block_class("FWHCondensing0D", doc=
"""Feedwater Heater Condensing Section
The feedwater heater condensing section model is a normal 0D heat exchanger
model with an added constraint to calculate the steam flow such that the outlet
of side_1 is a saturated liquid.""")
class FWHCondensing0DData(HeatExchangerData):
    def build(self):
        super().build()
        @self.Constraint(self.flowsheet().config.time,
            doc="Calculate steam extraction rate such that all steam condenses")
        def extraction_rate_constraint(b, t):
            return b.side_1.properties_out[t].enth_mol_sat_phase["Liq"] == \
                   b.side_1.properties_out[t].enth_mol

    def initialize(self, *args, **kwargs):
        """
        Use the regular heat exchanger initilization, with the extraction rate
        constraint deactivated; then it activates the constraint and calculates
        a steam inlet flow rate.
        """
        self.extraction_rate_constraint.deactivate()
        super().initialize(*args, **kwargs)
        self.extraction_rate_constraint.activate()

        solver = kwargs.get("solver", "ipopt")
        optarg = kwargs.get("oparg", {})
        outlvl = kwargs.get("outlvl", 0)

        opt = SolverFactory(solver)
        opt.options = optarg
        tee = True if outlvl >= 3 else False
        sp = StoreSpec.value_isfixed_isactive(only_fixed=True)
        istate = to_json(self, return_dict=True, wts=sp)

        self.area.fix()
        self.overall_heat_transfer_coefficient.fix()
        self.inlet_1.fix()
        self.inlet_2.fix()
        self.outlet_1.unfix()
        self.outlet_2.unfix()
        self.inlet_1.flow_mol.unfix()
        results = opt.solve(self, tee=tee)

        if results.solver.termination_condition == TerminationCondition.optimal:
            if outlvl >= 2:
                _log.info('{} Initialization Failed.'.format(self.name))
        else:
            _log.warning('{} Initialization Failed.'.format(self.name))

        from_json(self, sd=istate, wts=sp)


@declare_process_block_class("FWH0D", doc="""Feedwater Heater Model
This is a 0D feedwater heater model.  The model may contain three 0D heat
exchanger models representing the desuperheat, condensing and drain cooling
sections of the feedwater heater. Only the condensing section must be included.
A drain mixer can also be optionally included, which mixes the drain outlet of
another feedwater heater with the steam fed into the condensing section.
""")
class FWH0DData(UnitModelBlockData):
    CONFIG = UnitModelBlockData.CONFIG()
    _define_feedwater_heater_0D_config(CONFIG)

    def build(self):
        super().build()
        config = self.config # sorter ref to config for less line splitting

        # All feedwater heaters have a condensing section
        _set_prop_pack(config.condense, config)
        self.condense = FWHCondensing0D(default=config.condense)

        # Add a mixer to add the drain stream from another feedwater heater
        if config.has_drain_mixer:
            mix_cfg = { # general unit model config
                "dynamic":config.dynamic,
                "has_holdup":config.has_holdup,
                "property_package":config.property_package,
                "property_package_args":config.property_package_args,
                "momentum_mixing_type":MomentumMixingType.none,
                "inlet_list":["steam", "drain"]}
            self.drain_mix = Mixer(default=mix_cfg)
            @self.drain_mix.Constraint(self.drain_mix.flowsheet().config.time)
            def mixer_pressure_constraint(b, t):
                """
                Constraint to set the drain mixer pressure to the pressure of
                the steam extracted from the turbine. The drain inlet should
                always be a higher pressure than the steam inlet.
                """
                return b.steam_state[t].pressure == b.mixed_state[t].pressure
            # Connect the mixer to the condensing section inlet
            self.mix_out_arc = Arc(source=self.drain_mix.outlet,
                                   destination=self.condense.inlet_1)

        # Add a desuperheat section before the condensing section
        if config.has_desuperheat:
            _set_prop_pack(config.desuperheat, config)
            self.desuperheat = HeatExchanger(default=config.desuperheat)
            # set default area less than condensing section area, this will
            # almost always be overridden by the user fixing an area later
            self.desuperheat.area.value = 10
            if config.has_drain_mixer:
                self.desuperheat_drain_arc = Arc(
                    source=self.desuperheat.outlet_1,
                    destination=self.drain_mix.steam)
            else:
                self.desuperheat_drain_arc = Arc(
                    source=self.desuperheat.outlet_1,
                    destination=self.condense.inlet_1)
            self.condense_out2_arc = Arc(
                source=self.condense.outlet_2,
                destination=self.desuperheat.inlet_2)

        # Add a drain cooling section after the condensing section
        if config.has_drain_cooling:
            _set_prop_pack(config.cooling, config)
            self.cooling = HeatExchanger(default=config.cooling)
            # set default area less than condensing section area, this will
            # almost always be overridden by the user fixing an area later
            self.cooling.area.value = 10
            self.cooling_out2_arc = Arc(
                source=self.cooling.outlet_2,
                destination=self.condense.inlet_2)
            self.condense_out1_arc = Arc(
                source=self.condense.outlet_1,
                destination=self.cooling.inlet_1)

        TransformationFactory("network.expand_arcs").apply_to(self)

    def initialize(self, *args, **kwargs):
        config = self.config # sorter ref to config for less line splitting
        sp = StoreSpec.value_isfixed_isactive(only_fixed=True)
        istate = to_json(self, return_dict=True, wts=sp)

        # the initilization here isn't straight forward since the heat exchanger
        # may have 3 stages and they are countercurrent.  For simplicity each
        # stage in initialized with the same cooling water inlet conditions then
        # the whole feedwater heater is solved together.  There are more robust
        # approaches which can be implimented if the need arises.

        # initialize desuperheat if include
        if config.has_desuperheat:
            if config.has_drain_cooling:
                _set_port(self.desuperheat.inlet_2, self.cooling.inlet_2)
            else:
                _set_port(self.desuperheat.inlet_2, self.condense.inlet_2)
            self.desuperheat.initialize(*args, **kwargs)
            self.desuperheat.inlet_1.flow_mol.unfix()
            if config.has_drain_mixer:
                _set_port(self.drain_mix.steam, self.desuperheat.outlet_1)
            else:
                _set_port(self.condense.inlet_1, self.desuperheat.outlet_1)
            # fix the steam and fwh inlet for init
            self.desuperheat.inlet_1.fix()
            self.desuperheat.inlet_1.flow_mol.unfix() #unfix for extract calc

        # initialize mixer if included
        if config.has_drain_mixer:
            self.drain_mix.steam.fix()
            self.drain_mix.drain.fix()
            self.drain_mix.outlet.unfix()
            self.drain_mix.initialize(*args, **kwargs)
            _set_port(self.condense.inlet_1, self.drain_mix.outlet)
            if config.has_desuperheat:
                self.drain_mix.steam.unfix()
            else:
                self.drain_mix.steam.flow_mol.unfix()
        # Initialize condense section
        if config.has_drain_cooling:
            _set_port(self.condense.inlet_2, self.cooling.inlet_2)
            self.cooling.inlet_2.fix()
        else:
            self.condense.inlet_2.fix()
        self.condense.initialize(*args, **kwargs)
        # Initialize drain cooling if included
        if config.has_drain_cooling:
            _set_port(self.cooling.inlet_1, self.condense.outlet_1)
            self.cooling.initialize(*args, **kwargs)

        # Solve all together
        outlvl = kwargs.get("outlvl", 0)
        opt = SolverFactory(kwargs.get("solver", "ipopt"))
        opt.options = kwargs.get("oparg", {})
        tee = True if outlvl >= 3 else False
        assert(degrees_of_freedom(self)==0)
        results = opt.solve(self, tee=tee)
        if results.solver.termination_condition == TerminationCondition.optimal:
            if outlvl >= 2:
                _log.info('{} Initialization Complete.'.format(self.name))
        else:
            _log.warning('{} Initialization Failed.'.format(self.name))

        from_json(self, sd=istate, wts=sp)
