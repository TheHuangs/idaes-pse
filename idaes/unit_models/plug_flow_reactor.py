##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes".
##############################################################################
"""
Standard IDAES PFR model.
"""
from __future__ import division

# Import Pyomo libraries
from pyomo.common.config import ConfigBlock, ConfigValue, In

# Import IDAES cores
from idaes.core import (ControlVolume1D,
                        declare_process_block_class,
                        MaterialBalanceType,
                        EnergyBalanceType,
                        MomentumBalanceType,
                        UnitBlockData,
                        useDefault)
from idaes.core.util.config import (is_physical_parameter_block,
                                    is_reaction_parameter_block,
                                    list_of_floats)
from idaes.core.util.misc import add_object_reference

__author__ = "Andrew Lee, John Eslick"


@declare_process_block_class("PFR")
class PFRData(UnitBlockData):
    """
    Standard Plug Flow Reactor Unit Model Class
    """
    CONFIG = ConfigBlock()
    CONFIG.declare("dynamic", ConfigValue(
        default=useDefault,
        domain=In([useDefault, True, False]),
        description="Dynamic model flag",
        doc="""Indicates whether this model will be dynamic or not,
**default** = useDefault.
**Valid values:** {
**useDefault** - get flag from parent (default = False),
**True** - set as a dynamic model,
**False** - set as a steady-state model.}"""))
    CONFIG.declare("has_holdup", ConfigValue(
        default=False,
        domain=In([True, False]),
        description="Holdup construction flag",
        doc="""Indicates whether holdup terms should be constructed or not.
Must be True if dynamic = True,
**default** - False.
**Valid values:** {
**True** - construct holdup terms,
**False** - do not construct holdup terms}"""))
    CONFIG.declare("material_balance_type", ConfigValue(
        default=MaterialBalanceType.componentPhase,
        domain=In(MaterialBalanceType),
        description="Material balance construction flag",
        doc="""Indicates what type of mass balance should be constructed,
**default** - MaterialBalanceType.componentPhase.
**Valid values:** {
**MaterialBalanceType.none** - exclude material balances,
**MaterialBalanceType.componentPhase** - use phase component balances,
**MaterialBalanceType.componentTotal** - use total component balances,
**MaterialBalanceType.elementTotal** - use total element balances,
**MaterialBalanceType.total** - use total material balance.}"""))
    CONFIG.declare("energy_balance_type", ConfigValue(
        default=EnergyBalanceType.enthalpyTotal,
        domain=In(EnergyBalanceType),
        description="Energy balance construction flag",
        doc="""Indicates what type of energy balance should be constructed,
**default** - EnergyBalanceType.enthalpyTotal.
**Valid values:** {
**EnergyBalanceType.none** - exclude energy balances,
**EnergyBalanceType.enthalpyTotal** - single ethalpy balance for material,
**EnergyBalanceType.enthalpyPhase** - ethalpy balances for each phase,
**EnergyBalanceType.energyTotal** - single energy balance for material,
**EnergyBalanceType.energyPhase** - energy balances for each phase.}"""))
    CONFIG.declare("momentum_balance_type", ConfigValue(
        default=MomentumBalanceType.pressureTotal,
        domain=In(MomentumBalanceType),
        description="Momentum balance construction flag",
        doc="""Indicates what type of momentum balance should be constructed,
**default** - MomentumBalanceType.pressureTotal.
**Valid values:** {
**MomentumBalanceType.none** - exclude momentum balances,
**MomentumBalanceType.pressureTotal** - single pressure balance for material,
**MomentumBalanceType.pressurePhase** - pressure balances for each phase,
**MomentumBalanceType.momentumTotal** - single momentum balance for material,
**MomentumBalanceType.momentumPhase** - momentum balances for each phase.}"""))
    CONFIG.declare("has_equilibrium_reactions", ConfigValue(
        default=True,
        domain=In([True, False]),
        description="Equilibrium reaction construction flag",
        doc="""Indicates whether terms for equilibrium controlled reactions
should be constructed,
**default** - True.
**Valid values:** {
**True** - include equilibrium reaction terms,
**False** - exclude equilibrium reaction terms.}"""))
    CONFIG.declare("has_heat_of_reaction", ConfigValue(
        default=False,
        domain=In([True, False]),
        description="Heat of reaction term construction flag",
        doc="""Indicates whether terms for heat of reaction terms should be
constructed,
**default** - False.
**Valid values:** {
**True** - include heat of reaction terms,
**False** - exclude heat of reaction terms.}"""))
    CONFIG.declare("has_heat_transfer", ConfigValue(
        default=False,
        domain=In([True, False]),
        description="Heat transfer term construction flag",
        doc="""Indicates whether terms for heat transfer should be constructed,
**default** - False.
**Valid values:** {
**True** - include heat transfer terms,
**False** - exclude heat transfer terms.}"""))
    CONFIG.declare("has_pressure_change", ConfigValue(
        default=False,
        domain=In([True, False]),
        description="Pressure change term construction flag",
        doc="""Indicates whether terms for pressure change should be
constructed,
**default** - False.
**Valid values:** {
**True** - include pressure change terms,
**False** - exclude pressure change terms.}"""))
    CONFIG.declare("property_package", ConfigValue(
        default=useDefault,
        domain=is_physical_parameter_block,
        description="Property package to use for control volume",
        doc="""Property parameter object used to define property calculations,
**default** - useDefault.
**Valid values:** {
**useDefault** - use default package from parent model or flowsheet,
**PropertyParameterObject** - a PropertyParameterBlock object.}"""))
    CONFIG.declare("property_package_args", ConfigBlock(
        implicit=True,
        description="Arguments to use for constructing property packages",
        doc="""A ConfigBlock with arguments to be passed to a property block(s)
and used when constructing these,
**default** - None.
**Valid values:** {
see property package for documentation.}"""))
    CONFIG.declare("reaction_package", ConfigValue(
        default=None,
        domain=is_reaction_parameter_block,
        description="Reaction package to use for control volume",
        doc="""Reaction parameter object used to define reaction calculations,
**default** - None.
**Valid values:** {
**None** - no reaction package,
**ReactionParameterBlock** - a ReactionParameterBlock object.}"""))
    CONFIG.declare("reaction_package_args", ConfigBlock(
        implicit=True,
        description="Arguments to use for constructing reaction packages",
        doc="""A ConfigBlock with arguments to be passed to a reaction block(s)
and used when constructing these,
**default** - None.
**Valid values:** {
see reaction package for documentation.}"""))
    CONFIG.declare("length_domain_set", ConfigValue(
        default=[0.0, 1.0],
        domain=list_of_floats,
        description="List of points to use to initialize length domain",
        doc="""A list of values to be used when constructing the length domain
of the reactor. Point must lie between 0.0 and 1.0,
**default** - [0.0, 1.0].
**Valid values:** {
a list of floats}"""))
    CONFIG.declare("transformation_method", ConfigValue(
        default="dae.finite_difference",
        description="Method to use for DAE transformation",
        doc="""Method to use to transform domain. Must be a method recognised
by the Pyomo TransformationFactory,
**default** - "dae.finite_difference"."""))
    CONFIG.declare("transformation_scheme", ConfigValue(
        default="BACKWARD",
        description="Scheme to use for DAE transformation",
        doc="""Scheme to use when transformating domain. See Pyomo
documentation for supported schemes,
**default** - "BACKWARD"."""))
    CONFIG.declare("finite_elements", ConfigValue(
        default=20,
        description="Number of finite elements to use for DAE transformation",
        doc="""Number of finite elements to use when transforming length
domain,
**default** - 20."""))
    CONFIG.declare("collocation_points", ConfigValue(
        default=3,
        description="No. collocation points to use for DAE transformation",
        doc="""Number of collocation points to use when transforming length
domain,
**default** - 3."""))

    def build(self):
        """
        Begin building model (pre-DAE transformation).

        Args:
            None

        Returns:
            None
        """
        # Call UnitModel.build to setup dynamics
        super(PFRData, self).build()

        # Build Control Volume
        self.control_volume = ControlVolume1D(default={
                "dynamic": self.config.dynamic,
                "has_holdup": self.config.has_holdup,
                "property_package": self.config.property_package,
                "property_package_args": self.config.property_package_args,
                "reaction_package": self.config.reaction_package,
                "reaction_package_args": self.config.reaction_package_args})

        self.control_volume.add_geometry(
                length_domain_set=self.config.length_domain_set)

        self.control_volume.add_state_blocks()

        self.control_volume.add_reaction_blocks(
                has_equilibrium=self.config.has_equilibrium_reactions)

        self.control_volume.add_material_balances(
            balance_type=self.config.material_balance_type,
            has_rate_reactions=True,
            has_equilibrium_reactions=self.config.has_equilibrium_reactions)

        self.control_volume.add_energy_balances(
            balance_type=self.config.energy_balance_type,
            has_heat_of_reaction=self.config.has_heat_of_reaction,
            has_heat_transfer=self.config.has_heat_transfer)

        self.control_volume.add_momentum_balances(
            balance_type=self.config.momentum_balance_type,
            has_pressure_change=self.config.has_pressure_change)

        self.control_volume.apply_transformation(
                transformation_method=self.config.transformation_method,
                transformation_scheme=self.config.transformation_scheme,
                finite_elements=self.config.finite_elements,
                collocation_points=self.config.collocation_points)

        # Add Ports
        self.add_inlet_port()
        self.add_outlet_port()

        # Add performance equations
        add_object_reference(self,
                             "component_list_ref",
                             self.control_volume.component_list_ref)
        add_object_reference(self,
                             "phase_list_ref",
                             self.control_volume.phase_list_ref)
        add_object_reference(self,
                             "rate_reaction_idx_ref",
                             self.config.reaction_package.rate_reaction_idx)

        # Add PFR performance equation
        @self.Constraint(self.time_ref,
                         self.control_volume.length_domain,
                         self.rate_reaction_idx_ref,
                         doc="PFR performance equation")
        def performance_eqn(b, t, x, r):
            return b.control_volume.rate_reaction_extent[t, x, r] == (
                    b.control_volume.reactions[t, x].reaction_rate[r] *
                    b.control_volume.area)

        # Set references to balance terms at unit level
        add_object_reference(self,
                             "length",
                             self.control_volume.length)
        add_object_reference(self,
                             "area",
                             self.control_volume.area)
        add_object_reference(self,
                             "volume",
                             self.control_volume.volume)
        if (self.config.has_heat_transfer is True and
                self.config.energy_balance_type != 'none'):
            add_object_reference(self, "heat_duty", self.control_volume.heat)
        if (self.config.has_pressure_change is True and
                self.config.momentum_balance_type != 'none'):
            add_object_reference(self, "deltaP", self.control_volume.deltaP)