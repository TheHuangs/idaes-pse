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
Standard IDAES Feed block with phase equilibrium.
"""
from __future__ import division

# Import Pyomo libraries
from pyomo.environ import Reference
from pyomo.common.config import ConfigBlock, ConfigValue, In

# Import IDAES cores
from idaes.core import (ControlVolume0DBlock,
                        declare_process_block_class,
                        MaterialBalanceType,
                        MomentumBalanceType,
                        UnitModelBlockData,
                        useDefault)
from idaes.core.util.config import (is_physical_parameter_block)

__author__ = "Andrew Lee"


@declare_process_block_class("FeedFlash")
class FeedFlashData(UnitModelBlockData):
    """
    Standard Feed block with phase equilibrium
    """
    CONFIG = ConfigBlock()
    CONFIG.declare("dynamic", ConfigValue(
        domain=In([False]),
        default=False,
        description="Dynamic model flag - must be False",
        doc="""Feed units do not support dynamic behavior."""))
    CONFIG.declare("has_holdup", ConfigValue(
        default=False,
        domain=In([False]),
        description="Holdup construction flag - must be False",
        doc="""Feed units do not have defined volume, thus this must be
False."""))
    CONFIG.declare("material_balance_type", ConfigValue(
        default=MaterialBalanceType.componentPhase,
        domain=In(MaterialBalanceType),
        description="Material balance construction flag",
        doc="""Indicates what type of material balance should be constructed,
**default** - MaterialBalanceType.componentPhase.
**Valid values:** {
**MaterialBalanceType.none** - exclude material balances,
**MaterialBalanceType.componentPhase** - use phase component balances,
**MaterialBalanceType.componentTotal** - use total component balances,
**MaterialBalanceType.elementTotal** - use total element balances,
**MaterialBalanceType.total** - use total material balance.}"""))
    CONFIG.declare("property_package", ConfigValue(
        default=useDefault,
        domain=is_physical_parameter_block,
        description="Property package to use for control volume",
        doc="""Property parameter object used to define property calculations,
**default** - useDefault.
**Valid values:** {
**useDefault** - use default package from parent model or flowsheet,
**PhysicalParameterObject** - a PhysicalParameterBlock object.}"""))
    CONFIG.declare("property_package_args", ConfigBlock(
        implicit=True,
        description="Arguments to use for constructing property packages",
        doc="""A ConfigBlock with arguments to be passed to a property block(s)
and used when constructing these,
**default** - None.
**Valid values:** {
see property package for documentation.}"""))

    def build(self):
        """
        Begin building model.

        Args:
            None

        Returns:
            None
        """
        # Call UnitModel.build to setup dynamics
        super(FeedFlashData, self).build()

        # Build Control Volume
        self.control_volume = ControlVolume0DBlock(default={
                "dynamic": self.config.dynamic,
                "has_holdup": self.config.has_holdup,
                "property_package": self.config.property_package,
                "property_package_args": self.config.property_package_args})

        # No need for control volume geometry

        self.control_volume.add_state_blocks(
                has_phase_equilibrium=True)

        self.control_volume.add_material_balances(
            balance_type=self.config.material_balance_type,
            has_phase_equilibrium=True)

        # Add isothermal constraint
        @self.Constraint(self.flowsheet().config.time,
                         doc="Isothermal constraint")
        def isothermal(b, t):
            return (b.control_volume.properties_in[t].temperature ==
                    b.control_volume.properties_out[t].temperature)

        self.control_volume.add_momentum_balances(
            balance_type=MomentumBalanceType.pressureTotal)

        # Add references to all feed state vars
        s_vars = self.control_volume.properties_in[
                    self.flowsheet().config.time.first()].define_state_vars()
        for s in s_vars:
            l_name = s_vars[s].local_name
            if s_vars[s].is_indexed():
                slicer = (
                self.control_volume.properties_in[:].component(l_name)[...])
            else:
                slicer = self.control_volume.properties_in[:].component(l_name)

            r = Reference(slicer)
            setattr(self, s, r)

        # Add Ports
        self.add_outlet_port()

