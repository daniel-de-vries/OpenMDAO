from __future__ import print_function, division, absolute_import

import unittest

from openmdao.devtools.testutil import assert_rel_error

from openmdao.api import Problem, ScipyOptimizer, IndepVarComp

class TestBetzLimit(unittest.TestCase):

    def test_betz(self):
        from openmdao.api import Problem, ScipyOptimizer, IndepVarComp, ExplicitComponent

        class ActuatorDisc(ExplicitComponent):
            """Simple wind turbine model based on actuator disc theory"""

            def setup(self):

                # Inputs
                self.add_input('a', 0.5, desc="Induced Velocity Factor")
                self.add_input('Area', 10.0, units="m**2", desc="Rotor disc area")
                self.add_input('rho', 1.225, units="kg/m**3", desc="air density")
                self.add_input('Vu', 10.0, units="m/s", desc="Freestream air velocity, upstream of rotor")

                # Outputs
                self.add_output('Vr', 0.0, units="m/s",
                                desc="Air velocity at rotor exit plane")
                self.add_output('Vd', 0.0, units="m/s",
                                desc="Slipstream air velocity, downstream of rotor")
                self.add_output('Ct', 0.0, desc="Thrust Coefficient")
                self.add_output('thrust', 0.0, units="N",
                                desc="Thrust produced by the rotor")
                self.add_output('Cp', 0.0, desc="Power Coefficient")
                self.add_output('power', 0.0, units="W", desc="Power produced by the rotor")

                # self.declare_partials('*', '*', method='fd')

            def compute(self, inputs, outputs):
                """ Considering the entire rotor as a single disc that extracts
                velocity uniformly from the incoming flow and converts it to
                power."""

                a = inputs['a']
                Vu = inputs['Vu']

                qA = .5 * inputs['rho'] * inputs['Area'] * Vu ** 2

                outputs['Vd'] = Vd = Vu * (1 - 2 * a)
                outputs['Vr'] = .5 * (Vu + Vd)

                outputs['Ct'] = Ct = 4 * a * (1 - a)
                outputs['thrust'] = Ct * qA

                outputs['Cp'] = Cp = Ct * (1 - a)
                outputs['power'] = Cp * qA * Vu

            def compute_partials(self, inputs, J):
                """ Jacobian of partial derivatives."""

                a = inputs['a']
                Vu = inputs['Vu']
                Area = inputs['Area']
                rho = inputs['rho']

                # pre-compute commonly needed quantities
                a_times_area = a * Area
                one_minus_a = 1.0 - a
                a_area_rho_vu = a_times_area * rho * Vu

                J['Vr', 'a'] = -Vu
                J['Vr', 'Vu'] = one_minus_a

                J['Vd', 'a'] = -2.0 * Vu

                J['Ct', 'a'] = 4.0 - 8.0 * a

                J['thrust', 'a'] = .5 * rho * Vu**2 * Area * J['Ct', 'a']
                J['thrust', 'Area'] = 2.0 * Vu ** 2 * a * rho * one_minus_a
                J['thrust', 'rho'] = 2.0 * a_times_area * Vu ** 2 * (one_minus_a)
                J['thrust', 'Vu'] = 4.0 * a_area_rho_vu * (one_minus_a)

                J['Cp', 'a'] = 4.0 * a * (2.0 * a - 2.0) + 4.0 * (one_minus_a) ** 2

                J['power', 'a'] = 2.0 * Area * Vu ** 3 * a * rho * (
                2.0 * a - 2.0) + 2.0 * Area * Vu ** 3 * rho * one_minus_a ** 2
                J['power', 'Area'] = 2.0 * Vu ** 3 * a * rho * one_minus_a ** 2
                J['power', 'rho'] = 2.0 * a_times_area * Vu ** 3 * (one_minus_a) ** 2
                J['power', 'Vu'] = 6.0 * Area * Vu ** 2 * a * rho * one_minus_a ** 2


        # build the model
        prob = Problem()
        indeps = prob.model.add_subsystem('indeps', IndepVarComp(), promotes=['*'])
        indeps.add_output('a', .5)
        indeps.add_output('Area', 10.0, units='m**2')
        indeps.add_output('rho', 1.225, units='kg/m**3')
        indeps.add_output('Vu', 10.0, units='m/s')

        prob.model.add_subsystem('a_disk', ActuatorDisc(),
                                promotes_inputs=['a', 'Area', 'rho', 'Vu'])

        # setup the optimization
        prob.driver = ScipyOptimizer()
        prob.driver.options['optimizer'] = 'SLSQP'

        prob.model.add_design_var('a', lower=0., upper=1.)
        prob.model.add_design_var('Area', lower=0., upper=1.)
        # negative one so we maximize the objective
        prob.model.add_objective('a_disk.Cp', scaler=-1)

        prob.setup()
        prob.run_driver()

        # minimum value
        assert_rel_error(self, prob['a_disk.Cp'], 16./27., 1e-4)

if __name__ == "__main__":

    unittest.main()