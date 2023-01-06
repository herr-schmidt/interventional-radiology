from __future__ import division
import logging
import re
import time
import pyomo.environ as pyo
import plotly.express as px
import pandas as pd
import datetime
from pyomo.opt import SolverStatus, TerminationCondition

from abc import ABC, abstractmethod

from planner.model import Patient


class Planner(ABC):

    DISCARDED = 0
    FREE = 1
    FIXED = 2

    def __init__(self, timeLimit, gap, solver):
        self.solver = pyo.SolverFactory(solver)
        if(solver == "cplex"):
            self.timeLimit = 'timelimit'
            self.gap = 'mipgap'
            self.solver.options['emphasis'] = "mip 2"
        if(solver == "gurobi"):
            self.timeLimit = 'timelimit'
            self.gap = 'mipgap'
            self.solver.options['mipfocus'] = 2
        if(solver == "cbc"):
            self.timeLimit = 'seconds'
            self.gap = 'ratiogap'
            self.solver.options['heuristics'] = "on"
            # self.solver.options['round'] = "on"
            # self.solver.options['feas'] = "on"
            self.solver.options['cuts'] = "on"
            self.solver.options['preprocess'] = "on"
            # self.solver.options['printingOptions'] = "normal"

        self.solver.options[self.timeLimit] = timeLimit
        self.solver.options[self.gap] = gap

    @abstractmethod
    def define_model(self):
        pass

    @staticmethod
    def single_surgery_rule(model, i):
        return sum(model.x[i, k, t] for k in model.k for t in model.t) <= 1

    @staticmethod
    def surgery_time_rule(model, k, t):
        return sum(model.p[i] * model.x[i, k, t] for i in model.i) <= model.s[k, t]

    @staticmethod
    def specialty_assignment_rule(model, j, k, t):
        return sum(model.x[i, k, t] for i in model.i if model.specialty[i] == j) <= model.bigM[1] * model.tau[j, k, t]

    @staticmethod
    def anesthetist_assignment_rule(model, i, t):
        if(model.a[i] == 0):
            return pyo.Constraint.Skip
        return sum(model.beta[alpha, i, t] for alpha in model.alpha) == model.a[i] * sum(model.x[i, k, t] for k in model.k)

    @staticmethod
    def anesthetist_time_rule(model, alpha, t):
        return sum(model.beta[alpha, i, t] * model.p[i] for i in model.i) <= model.An[alpha, t]

    # patients with same anesthetist on same day but different room cannot overlap
    @staticmethod
    @abstractmethod
    def anesthetist_no_overlap_rule(model, i1, i2, k1, k2, t, alpha):
        pass

    # precedence across rooms
    @staticmethod
    @abstractmethod
    def lambda_rule(model, i1, i2, t):
        pass

    # ensure gamma plus operation time does not exceed end of day
    @staticmethod
    @abstractmethod
    def end_of_day_rule(model, i, k, t):
        pass

    # ensure that patient i1 terminates operation before i2, if y_12kt = 1
    @staticmethod
    @abstractmethod
    def time_ordering_precedence_rule(model, i1, i2, k, t):
        pass

    @staticmethod
    @abstractmethod
    def start_time_ordering_priority_rule(model, i1, i2, k, t):
        pass

    # either i1 comes before i2 in (k, t) or i2 comes before i1 in (k, t)
    @staticmethod
    @abstractmethod
    def exclusive_precedence_rule(model, i1, i2, k, t):
        pass

    @staticmethod
    def objective_function(model):
        return sum(model.r[i] * model.x[i, k, t] for i in model.i for k in model.k for t in model.t)

    # constraints
    def define_single_surgery_constraints(self, model):
        model.single_surgery_constraint = pyo.Constraint(
            model.i,
            rule=self.single_surgery_rule)

    def define_surgery_time_constraints(self, model):
        model.surgery_time_constraint = pyo.Constraint(
            model.k,
            model.t,
            rule=self.surgery_time_rule)

    def define_specialty_assignment_constraints(self, model):
        model.specialty_assignment_constraint = pyo.Constraint(
            model.j,
            model.k,
            model.t,
            rule=self.specialty_assignment_rule)

    def define_anesthetist_assignment_constraint(self, model):
        model.anesthetist_assignment_constraint = pyo.Constraint(
            model.i,
            model.t,
            rule=self.anesthetist_assignment_rule)

    def define_anesthetist_time_constraint(self, model):
        model.anesthetist_time_constraint = pyo.Constraint(
            model.alpha,
            model.t,
            rule=self.anesthetist_time_rule)

    def define_anesthetist_no_overlap_constraint(self, model):
        model.anesthetist_no_overlap_constraint = pyo.Constraint(
            model.i,
            model.i,
            model.k,
            model.k,
            model.t,
            model.alpha,
            rule=self.anesthetist_no_overlap_rule)

    def define_lambda_constraint(self, model):
        model.lambda_constraint = pyo.Constraint(
            model.i,
            model.i,
            model.t,
            rule=self.lambda_rule)

    def define_end_of_day_constraint(self, model):
        model.end_of_day_constraint = pyo.Constraint(
            model.i,
            model.k,
            model.t,
            rule=self.end_of_day_rule)

    def define_priority_constraint(self, model):
        model.priority_constraint = pyo.Constraint(
            model.i,
            model.i,
            model.k,
            model.t,
            rule=self.start_time_ordering_priority_rule)

    def define_precedence_constraint(self, model):
        model.precedence_constraint = pyo.Constraint(
            model.i,
            model.i,
            model.k,
            model.t,
            rule=self.time_ordering_precedence_rule)

    def define_exclusive_precedence_constraint(self, model):
        model.exclusive_precedence_constraint = pyo.Constraint(
            model.i,
            model.i,
            model.k,
            model.t,
            rule=self.exclusive_precedence_rule)

    def define_objective(self, model):
        model.objective = pyo.Objective(
            rule=self.objective_function,
            sense=pyo.maximize)

    def define_lambda_variables(self, model):
        model.Lambda = pyo.Var(model.i,
                               model.i,
                               model.t,
                               domain=pyo.Binary)

    def define_y_variables(self, model):
        model.y = pyo.Var(model.i,
                          model.i,
                          model.k,
                          model.t,
                          domain=pyo.Binary)

    def define_gamma_variables(self, model):
        model.gamma = pyo.Var(model.i, domain=pyo.NonNegativeReals)

    def define_anesthetists_number_param(self, model):
        model.A = pyo.Param(within=pyo.NonNegativeIntegers)

    def define_anesthetists_range_set(self, model):
        model.alpha = pyo.RangeSet(1, model.A)

    def define_beta_variables(self, model):
        model.beta = pyo.Var(model.alpha,
                             model.i,
                             model.t,
                             domain=pyo.Binary)

    def define_anesthetists_availability(self, model):
        model.An = pyo.Param(model.alpha, model.t)

    def define_sets(self, model):
        model.I = pyo.Param(within=pyo.NonNegativeIntegers)
        model.J = pyo.Param(within=pyo.NonNegativeIntegers)
        model.K = pyo.Param(within=pyo.NonNegativeIntegers)
        model.T = pyo.Param(within=pyo.NonNegativeIntegers)
        model.M = pyo.Param(within=pyo.NonNegativeIntegers)

        model.i = pyo.RangeSet(1, model.I)
        model.j = pyo.RangeSet(1, model.J)
        model.k = pyo.RangeSet(1, model.K)
        model.t = pyo.RangeSet(1, model.T)
        model.bigMRangeSet = pyo.RangeSet(1, model.M)

    def define_x_variables(self, model):
        model.x = pyo.Var(model.i,
                          model.k,
                          model.t,
                          domain=pyo.Binary)

    def define_parameters(self, model):
        model.p = pyo.Param(model.i)
        model.r = pyo.Param(model.i)
        model.s = pyo.Param(model.k, model.t)
        model.a = pyo.Param(model.i)
        model.c = pyo.Param(model.i)
        model.u = pyo.Param(model.i, model.i)
        model.tau = pyo.Param(model.j, model.k, model.t)
        model.specialty = pyo.Param(model.i)
        model.bigM = pyo.Param(model.bigMRangeSet)
        model.d = pyo.Param(model.i)
        model.precedence = pyo.Param(model.i)


class SimplePlanner(Planner):

    def __init__(self, timeLimit, gap, solver):
        super().__init__(timeLimit, gap, solver)
        self.model = pyo.AbstractModel()
        self.modelInstance = None

    @staticmethod
    def anesthetist_no_overlap_rule(model, i1, i2, k1, k2, t, alpha):
        if(i1 == i2 or k1 == k2 or model.a[i1] * model.a[i2] == 0):
            return pyo.Constraint.Skip
        return model.gamma[i1] + model.p[i1] <= model.gamma[i2] + model.bigM[3] * (5 - model.beta[alpha, i1, t] - model.beta[alpha, i2, t] - model.x[i1, k1, t] - model.x[i2, k2, t] - model.Lambda[i1, i2, t])

    @staticmethod
    def lambda_rule(model, i1, i2, t):
        if(i1 >= i2 or not (model.a[i1] == 1 and model.a[i2] == 1)):
            return pyo.Constraint.Skip
        return model.Lambda[i1, i2, t] + model.Lambda[i2, i1, t] == 1

    @staticmethod
    def end_of_day_rule(model, i, k, t):
        if((model.specialty[i] == 1 and (k == 3 or k == 4))
           or (model.specialty[i] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i] + model.p[i] <= model.s[k, t]

    @staticmethod
    def time_ordering_precedence_rule(model, i1, i2, k, t):
        if(i1 == i2
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i1] + model.p[i1] <= model.gamma[i2] + model.bigM[5] * (3 - model.x[i1, k, t] - model.x[i2, k, t] - model.y[i1, i2, k, t])

    @staticmethod
    def start_time_ordering_priority_rule(model, i1, i2, k, t):
        if(i1 == i2 or model.u[i1, i2] == 0
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i1] * model.u[i1, i2] <= model.gamma[i2] * (1 - model.u[i2, i1]) + model.bigM[2] * (2 - model.x[i1, k, t] - model.x[i2, k, t])

    @staticmethod
    def exclusive_precedence_rule(model, i1, i2, k, t):
        if(i1 >= i2
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.y[i1, i2, k, t] + model.y[i2, i1, k, t] == 1

    def define_model(self):
        self.define_sets(self.model)
        self.define_x_variables(self.model)
        self.define_parameters(self.model)

        self.define_single_surgery_constraints(self.model)
        self.define_surgery_time_constraints(self.model)
        self.define_specialty_assignment_constraints(self.model)

        self.define_anesthetists_number_param(self.model)
        self.define_anesthetists_range_set(self.model)
        self.define_beta_variables(self.model)
        self.define_anesthetists_availability(self.model)
        self.define_lambda_variables(self.model)
        self.define_y_variables(self.model)
        self.define_gamma_variables(self.model)

        self.define_anesthetist_assignment_constraint(self.model)
        self.define_anesthetist_time_constraint(self.model)
        self.define_anesthetist_no_overlap_constraint(self.model)
        self.define_lambda_constraint(self.model)
        self.define_end_of_day_constraint(self.model)
        self.define_priority_constraint(self.model)
        self.define_precedence_constraint(self.model)
        self.define_exclusive_precedence_constraint(self.model)

        self.define_objective(self.model)

    def create_model_instance(self, data):
        print("Creating model instance...")
        t = time.time()
        self.modelInstance = self.model.create_instance(data)
        elapsed = (time.time() - t)
        return elapsed

    def fix_y_variables(self, modelInstance):
        print("Fixing y variables...")
        fixed = 0
        for k in modelInstance.k:
            for t in modelInstance.t:
                for i1 in range(2, self.modelInstance.I + 1):
                    for i2 in range(1, i1):
                        if(modelInstance.u[i1, i2] == 1):
                            modelInstance.y[i1, i2, k, t].fix(1)
                            modelInstance.y[i2, i1, k, t].fix(0)
                            fixed += 2
        print(str(fixed) + " y variables fixed.")

    def extract_solution(self):
        dict = {}
        for k in self.modelInstance.k:
            for t in self.modelInstance.t:
                patients = []
                for i in self.modelInstance.i:
                    if(round(self.modelInstance.x[i, k, t].value) == 1):
                        p = self.modelInstance.p[i]
                        c = self.modelInstance.c[i]
                        a = self.modelInstance.a[i]
                        anesthetist = 0
                        for alpha in self.modelInstance.alpha:
                            if(round(self.modelInstance.beta[alpha, i, t].value) == 1):
                                anesthetist = alpha
                        order = round(self.modelInstance.gamma[i].value)
                        specialty = self.modelInstance.specialty[i]
                        priority = self.modelInstance.r[i]
                        precedence = self.modelInstance.precedence[i]
                        patients.append(Patient(
                            i, priority, k, specialty, t, p, c, precedence, None, a, anesthetist, order))
                patients.sort(key=lambda x: x.order)
                dict[(k, t)] = patients
        return dict

    def solve_model(self, data):
        self.define_model()
        buildingTime = self.create_model_instance(data)
        self.fix_y_variables(self.modelInstance)
        print("Solving model instance...")
        self.model.results = self.solver.solve(self.modelInstance, tee=True)
        print("\nModel instance solved.")
        print(self.model.results)
        resultsAsString = str(self.model.results)
        upperBound = float(
            re.search("Upper bound: -*(\d*\.\d*)", resultsAsString).group(1))

        timeLimitHit = self.model.results.solver.termination_condition in [
            TerminationCondition.maxTimeLimit]
        status_ok = self.model.results.solver.status == SolverStatus.ok

        run_info = {"BuildingTime": buildingTime,
                    "status_ok": status_ok,
                    "SolverTime": self.solver._last_solve_time,
                    "TimeLimitHit": timeLimitHit,
                    "UpperBound": upperBound,
                    "Gap": round((1 - pyo.value(self.modelInstance.objective) / upperBound) * 100, 2)
                    }

        return run_info


class TwoPhasePlanner(Planner):

    def __init__(self, timeLimit, gap, solver):
        super().__init__(timeLimit, gap, solver)
        self.MP_model = pyo.AbstractModel()
        self.MP_instance = None
        self.SP_model = pyo.AbstractModel()
        self.SP_instance = None

    def define_model(self):
        self.define_MP()
        self.define_SP()

        self.define_objective(self.MP_model)
        self.define_objective(self.SP_model)

    def define_MP(self):
        self.define_sets(self.MP_model)
        self.define_x_variables(self.MP_model)
        self.define_parameters(self.MP_model)
        self.define_single_surgery_constraints(self.MP_model)
        self.define_surgery_time_constraints(self.MP_model)
        self.define_specialty_assignment_constraints(self.MP_model)
        self.define_anesthetists_number_param(self.MP_model)
        self.define_anesthetists_range_set(self.MP_model)
        self.define_beta_variables(self.MP_model)
        self.define_anesthetists_availability(self.MP_model)
        self.define_anesthetist_assignment_constraint(self.MP_model)
        self.define_anesthetist_time_constraint(self.MP_model)

        # self.define_objective(self.MP_model)

    def define_x_parameters(self):
        self.SP_model.x_param = pyo.Param(self.SP_model.i,
                                          self.SP_model.k,
                                          self.SP_model.t)

    def define_status_parameters(self):
        self.SP_model.status = pyo.Param(self.SP_model.i,
                                         self.SP_model.k,
                                         self.SP_model.t)

    def define_SP(self):
        self.define_sets(self.SP_model)
        self.define_x_variables(self.SP_model)
        self.define_parameters(self.SP_model)
        self.define_single_surgery_constraints(self.SP_model)
        self.define_surgery_time_constraints(self.SP_model)
        self.define_specialty_assignment_constraints(self.SP_model)
        self.define_anesthetists_number_param(self.SP_model)
        self.define_anesthetists_range_set(self.SP_model)
        self.define_beta_variables(self.SP_model)
        self.define_anesthetists_availability(self.SP_model)
        self.define_anesthetist_assignment_constraint(self.SP_model)
        self.define_anesthetist_time_constraint(self.SP_model)

        # SP's components
        self.define_x_parameters()
        self.define_status_parameters()
        self.define_lambda_variables(self.SP_model)
        self.define_y_variables(self.SP_model)
        self.define_gamma_variables(self.SP_model)
        self.define_anesthetist_no_overlap_constraint(self.SP_model)
        self.define_lambda_constraint(self.SP_model)
        self.define_end_of_day_constraint(self.SP_model)
        self.define_priority_constraint(self.SP_model)
        self.define_precedence_constraint(self.SP_model)
        self.define_exclusive_precedence_constraint(self.SP_model)

        # self.define_objective(self.SP_model)

    def create_MP_instance(self, data):
        print("Creating MP instance...")
        t = time.time()
        self.MP_instance = self.MP_model.create_instance(data)
        elapsed = (time.time() - t)
        print("MP instance created in " + str(round(elapsed, 2)) + "s")
        return elapsed

    def create_SP_instance(self, data):
        self.extend_data(data)
        print("Creating SP instance...")
        t = time.time()
        self.SP_instance = self.SP_model.create_instance(data)
        elapsed = (time.time() - t)
        print("SP instance created in " + str(round(elapsed, 2)) + "s")
        return elapsed

    def extract_solution(self):
        if(self.SP_model.results.solver.status != SolverStatus.ok):
            return None
        dict = {}
        for k in self.SP_instance.k:
            for t in self.SP_instance.t:
                patients = []
                for i in self.SP_instance.i:
                    if(round(self.SP_instance.x[i, k, t].value) == 1):
                        p = self.SP_instance.p[i]
                        c = self.SP_instance.c[i]
                        a = self.SP_instance.a[i]
                        anesthetist = 0
                        for alpha in self.SP_instance.alpha:
                            if(round(self.SP_instance.beta[alpha, i, t].value) == 1):
                                anesthetist = alpha
                        order = round(self.SP_instance.gamma[i].value, 2)
                        specialty = self.SP_instance.specialty[i]
                        priority = self.SP_instance.r[i]
                        precedence = self.SP_instance.precedence[i]
                        patients.append(Patient(
                            i, priority, k, specialty, t, p, c, precedence, None, a, anesthetist, order))
                patients.sort(key=lambda x: x.order)
                dict[(k, t)] = patients
        return dict


class TwoPhaseHeuristicPlanner(TwoPhasePlanner):

    @abstractmethod
    def fix_SP_x_variables(self):
        pass

    @abstractmethod
    def extend_data(self, data):
        pass

    @staticmethod
    def anesthetist_no_overlap_rule(model, i1, i2, k1, k2, t, alpha):
        if(model.status[i1, k1, t] == Planner.DISCARDED or model.status[i2, k2, t] == Planner.DISCARDED):
            return pyo.Constraint.Skip
        if(i1 == i2 or k1 == k2 or model.a[i1] * model.a[i2] == 0):
            return pyo.Constraint.Skip
        return model.gamma[i1] + model.p[i1] <= model.gamma[i2] + model.bigM[3] * (5 - model.beta[alpha, i1, t] - model.beta[alpha, i2, t] - model.x[i1, k1, t] - model.x[i2, k2, t] - model.Lambda[i1, i2, t])

    @staticmethod
    def end_of_day_rule(model, i, k, t):
        if(model.status[i, k, t] == Planner.DISCARDED):
            return pyo.Constraint.Skip
        if((model.specialty[i] == 1 and (k == 3 or k == 4))
           or (model.specialty[i] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i] + model.p[i] <= model.s[k, t]

    @staticmethod
    def time_ordering_precedence_rule(model, i1, i2, k, t):
        if(model.status[i1, k, t] == Planner.DISCARDED or model.status[i2, k, t] == Planner.DISCARDED):
            return pyo.Constraint.Skip
        if(i1 == i2
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i1] + model.p[i1] <= model.gamma[i2] + model.bigM[5] * (3 - model.x[i1, k, t] - model.x[i2, k, t] - model.y[i1, i2, k, t])

    @staticmethod
    def start_time_ordering_priority_rule(model, i1, i2, k, t):
        if(model.status[i1, k, t] == Planner.DISCARDED or model.status[i2, k, t] == Planner.DISCARDED):
            return pyo.Constraint.Skip
        if(i1 == i2 or model.u[i1, i2] == 0
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i1] * model.u[i1, i2] <= model.gamma[i2] * (1 - model.u[i2, i1]) + model.bigM[2] * (2 - model.x[i1, k, t] - model.x[i2, k, t])

    @staticmethod
    def exclusive_precedence_rule(model, i1, i2, k, t):
        if(model.specialty[i1] != model.specialty[i2]):
            return pyo.Constraint.Skip
        if(model.status[i1, k, t] == Planner.DISCARDED or model.status[i2, k, t] == Planner.DISCARDED):
            return pyo.Constraint.Skip
        if(i1 >= i2
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.y[i1, i2, k, t] + model.y[i2, i1, k, t] == 1

    def solve_model(self, data):
        self.define_model()
        MPBuildingTime = self.create_MP_instance(data)

        # MP
        print("Solving MP instance...")
        print(self.solver)
        self.MP_model.results = self.solver.solve(self.MP_instance, tee=True)
        print("\nMP instance solved.")
        MP_solver_time = self.solver._last_solve_time
        MP_time_limit_hit = self.MP_model.results.solver.termination_condition in [
            TerminationCondition.maxTimeLimit]
        resultsAsString = str(self.MP_model.results)
        MP_upper_bound = float(
            re.search("Upper bound: -*(\d*\.\d*)", resultsAsString).group(1))

        self.solver.options[self.timeLimit] = max(
            10, 600 - self.solver._last_solve_time)

        # SP
        SP_building_time = self.create_SP_instance(data)

        self.fix_SP_x_variables()
        print("Solving SP instance...")
        self.SP_model.results = self.solver.solve(self.SP_instance, tee=True)
        print("SP instance solved.")
        SP_solver_time = self.solver._last_solve_time
        SP_time_limit_hit = self.SP_model.results.solver.termination_condition in [
            TerminationCondition.maxTimeLimit]

        status_ok = self.SP_model.results.solver.status == SolverStatus.ok

        run_info = {"MP_solver_time": MP_solver_time,
                    "SP_solver_time": SP_solver_time,
                    "MPBuildingTime": MPBuildingTime,
                    "SP_building_time": SP_building_time,
                    "status_ok": status_ok,
                    "MP_time_limit_hit": MP_time_limit_hit,
                    "SP_time_limit_hit": SP_time_limit_hit,
                    "MPobjectiveValue": pyo.value(self.MP_instance.objective),
                    "SPobjectiveValue": pyo.value(self.SP_instance.objective),
                    "MP_upper_bound": MP_upper_bound,
                    "objectiveFunctionLB": 0}

        print(self.SP_model.results)
        return run_info


class FastCompleteHeuristicPlanner(TwoPhaseHeuristicPlanner):

    @staticmethod
    def lambda_rule(model, i1, i2, t):
        if(i1 >= i2 or not (model.a[i1] == 1 and model.a[i2] == 1)):
            return pyo.Constraint.Skip
        i1_all_day = 0
        i2_all_day = 0
        for k in model.k:
            # if i1, i2 happen to be assigned to same room k on day t, then no need to use constraint
            if(model.status[i1, k, t] == Planner.FIXED and model.status[i2, k, t] == Planner.FIXED):
                return pyo.Constraint.Skip
            if(model.status[i1, k, t] == Planner.FIXED or model.status[i1, k, t] == Planner.FREE):
                i1_all_day += 1
            if(model.status[i2, k, t] == Planner.FIXED or model.status[i2, k, t] == Planner.FREE):
                i2_all_day += 1
        if(i1_all_day == 0 or i2_all_day == 0):
            return pyo.Constraint.Skip
        return model.Lambda[i1, i2, t] + model.Lambda[i2, i1, t] == 1

    def extend_data(self, data):
        status_dict = {}
        for i in range(1, self.MP_instance.I + 1):
            for k in range(1, self.MP_instance.K + 1):
                for t in range(1, self.MP_instance.T + 1):
                    if(round(self.MP_instance.x[i, k, t].value) == 1 and self.MP_instance.a[i] == 1):
                        status_dict[(i, k, t)] = Planner.FREE
                    elif(round(self.MP_instance.x[i, k, t].value) == 1 and self.MP_instance.a[i] == 0):
                        status_dict[(i, k, t)] = Planner.FIXED
                    else:
                        status_dict[(i, k, t)] = Planner.DISCARDED
        data[None]['status'] = status_dict

    def fix_SP_x_variables(self):
        print("Fixing x variables for phase two...")
        fixed = 0
        for k in self.MP_instance.k:
            for t in self.MP_instance.t:
                for i1 in self.MP_instance.i:
                    if(round(self.MP_instance.x[i1, k, t].value) == 1 and self.SP_instance.a[i1] == 0):
                        self.SP_instance.x[i1, k, t].fix(1)
                        fixed += 1
                    if(round(self.MP_instance.x[i1, k, t].value) == 0):
                        self.SP_instance.x[i1, k, t].fix(0)
                        fixed += 1
        print(str(fixed) + " x variables fixed.")


class FastCompleteLagrangeanHeuristicPlanner(FastCompleteHeuristicPlanner):

    @staticmethod
    def objective_function_MP(model):
        return sum(model.r[i] * model.x[i, k, t] for i in model.i for k in model.k for t in model.t) + 1 / (sum(model.An[alpha, t] for alpha in model.alpha for t in model.t) + sum(model.p[i] for i in model.i)) * sum(model.An[alpha, t] - sum(model.beta[alpha, i, t] * model.p[i] for i in model.t) for alpha in model.alpha for t in model.t)

    def define_objective_MP(self, model):
        model.objective = pyo.Objective(
            rule=self.objective_function_MP,
            sense=pyo.maximize)

    def define_model(self):
        self.define_MP()
        self.define_SP()

        self.define_objective_MP(self.MP_model)
        self.define_objective(self.SP_model)


class SlowCompleteHeuristicPlanner(TwoPhaseHeuristicPlanner):

    @staticmethod
    def lambda_rule(model, i1, i2, t):
        if(i1 >= i2 or not (model.a[i1] == 1 and model.a[i2] == 1)):
            return pyo.Constraint.Skip
        # if patients not on same day
        if(sum(model.x_param[i1, k, t] for k in model.k) == 0 or sum(model.x_param[i2, k, t] for k in model.k) == 0):
            return pyo.Constraint.Skip
        return model.Lambda[i1, i2, t] + model.Lambda[i2, i1, t] == 1

    def extend_data(self, data):
        x_param_dict = {}
        status_dict = {}
        for i in self.MP_instance.i:
            for t in self.MP_instance.t:
                # patient scheduled on day t
                if(sum(round(self.MP_instance.x[i, k, t].value) for k in self.MP_instance.k) == 1):
                    for k in range(1, self.MP_instance.K + 1):
                        status_dict[(i, k, t)] = Planner.FREE
                        x_param_dict[(i, k, t)] = 1
                else:
                    for k in range(1, self.MP_instance.K + 1):
                        status_dict[(i, k, t)] = Planner.DISCARDED
                        x_param_dict[(i, k, t)] = 0
        data[None]['x_param'] = x_param_dict
        data[None]['status'] = status_dict

    def fix_SP_x_variables(self):
        print("Fixing x variables for phase two...")
        fixed = 0
        for k in self.MP_instance.k:
            for t in self.MP_instance.t:
                for i in self.MP_instance.i:
                    if(self.SP_instance.status[i, k, t] == Planner.DISCARDED):
                        self.SP_instance.x[i, k, t].fix(0)
                        fixed += 1
        print(str(fixed) + " x variables fixed.")


class SlowCompleteLagrangeanHeuristicPlanner(SlowCompleteHeuristicPlanner):

    @staticmethod
    def objective_function_MP(model):
        return sum(model.r[i] * model.x[i, k, t] for i in model.i for k in model.k for t in model.t) + 1 / (sum(model.An[alpha, t] for alpha in model.alpha for t in model.t) + sum(model.p[i] for i in model.i)) * sum(model.An[alpha, t] - sum(model.beta[alpha, i, t] * model.p[i] for i in model.t) for alpha in model.alpha for t in model.t)

    def define_objective_MP(self, model):
        model.objective = pyo.Objective(
            rule=self.objective_function_MP,
            sense=pyo.maximize)

    def define_model(self):
        self.define_MP()
        self.define_SP()

        self.define_objective_MP(self.MP_model)
        self.define_objective(self.SP_model)


class LBBDPlanner(TwoPhasePlanner):

    def __init__(self, timeLimit, gap, iterations_cap, solver):
        self.iterations_cap = iterations_cap
        super().__init__(timeLimit, gap, solver)

    # patients with same anesthetist on same day but different room cannot overlap
    @staticmethod
    def anesthetist_no_overlap_rule(model, i1, i2, k1, k2, t, alpha):
        if(i1 == i2 or k1 == k2 or model.a[i1] * model.a[i2] == 0
           or (model.x_param[i1, k1, t] + model.x_param[i2, k2, t] < 2)):
            return pyo.Constraint.Skip
        return model.gamma[i1] + model.p[i1] <= model.gamma[i2] + model.bigM[3] * (5 - model.beta[alpha, i1, t] - model.beta[alpha, i2, t] - model.x[i1, k1, t] - model.x[i2, k2, t] - model.Lambda[i1, i2, t])

    # precedence across rooms
    @staticmethod
    def lambda_rule(model, i1, i2, t):
        if(i1 >= i2 or not (model.a[i1] == 1 and model.a[i2] == 1)):
            return pyo.Constraint.Skip
        i1_all_day = 0
        i2_all_day = 0
        for k in model.k:
            # if i1, i2 happen to be assigned to same room k on day t, then no need to use constraint
            if(model.x_param[i1, k, t] + model.x_param[i2, k, t] == 2):
                return pyo.Constraint.Skip
            i1_all_day += model.x_param[i1, k, t]
            i2_all_day += model.x_param[i2, k, t]
        if(i1_all_day == 0 or i2_all_day == 0):
            return pyo.Constraint.Skip
        return model.Lambda[i1, i2, t] + model.Lambda[i2, i1, t] == 1

    # ensure gamma plus operation time does not exceed end of day
    @staticmethod
    def end_of_day_rule(model, i, k, t):
        if(model.find_component('x_param') and model.x_param[i, k, t] == 0
           or (model.specialty[i] == 1 and (k == 3 or k == 4))
           or (model.specialty[i] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i] + model.p[i] <= model.s[k, t]

    # ensure that patient i1 terminates operation before i2, if y_12kt = 1
    @staticmethod
    def time_ordering_precedence_rule(model, i1, i2, k, t):
        if(i1 == i2 or (model.find_component('x_param') and model.x_param[i1, k, t] + model.x_param[i2, k, t] < 2)
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i1] + model.p[i1] <= model.gamma[i2] + model.bigM[5] * (3 - model.x[i1, k, t] - model.x[i2, k, t] - model.y[i1, i2, k, t])

    @staticmethod
    def start_time_ordering_priority_rule(model, i1, i2, k, t):
        if(i1 == i2 or model.u[i1, i2] == 0 or (model.x_param[i1, k, t] + model.x_param[i2, k, t] < 2)
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.gamma[i1] * model.u[i1, i2] <= model.gamma[i2] * (1 - model.u[i2, i1]) + model.bigM[2] * (2 - model.x[i1, k, t] - model.x[i2, k, t])

    # either i1 comes before i2 in (k, t) or i2 comes before i1 in (k, t)
    @staticmethod
    def exclusive_precedence_rule(model, i1, i2, k, t):
        if(i1 >= i2 or (model.find_component('x_param') and model.x_param[i1, k, t] + model.x_param[i2, k, t] < 2)
           or (model.specialty[i1] != model.specialty[i2])
           or (model.specialty[i1] == 1 and (k == 3 or k == 4))
           or (model.specialty[i1] == 2 and (k == 1 or k == 2))):
            return pyo.Constraint.Skip
        return model.y[i1, i2, k, t] + model.y[i2, i1, k, t] == 1

    def fix_SP_x_variables(self):
        print("Fixing x variables for SP...")
        fixed = 0
        for k in self.MP_instance.k:
            for t in self.MP_instance.t:
                for i1 in self.MP_instance.i:
                    if(round(self.MP_instance.x[i1, k, t].value) == 1):
                        self.SP_instance.x[i1, k, t].fix(1)
                    else:
                        self.SP_instance.x[i1, k, t].fix(0)
                    fixed += 1
        print(str(fixed) + " x variables fixed.")

    def extend_data(self, data):
        dict = {}
        for i in range(1, self.MP_instance.I + 1):
            for k in range(1, self.MP_instance.K + 1):
                for t in range(1, self.MP_instance.T + 1):
                    if(round(self.MP_instance.x[i, k, t].value) == 1):
                        dict[(i, k, t)] = 1
                    else:
                        dict[(i, k, t)] = 0
        data[None]['x_param'] = dict

    def solve_model(self, data):
        self.define_MP()
        self.define_SP()
        MPBuildingTime = self.create_MP_instance(data)
        self.MP_instance.cuts = pyo.ConstraintList()

        solverTime = 0
        iterations = 0
        total_SP_building_time = 0
        MP_time_limit_hit = False
        SP_time_limit_hit = False
        worstMPBoundTimeLimitHit = 0
        fail = False
        objectiveValue = -1
        while iterations < self.iterations_cap:
            iterations += 1
            # MP
            print("Solving MP instance...")
            self.MP_model.results = self.solver.solve(
                self.MP_instance, tee=True)
            print("\nMP instance solved.")
            solverTime += self.solver._last_solve_time
            MP_time_limit_hit = MP_time_limit_hit or self.MP_model.results.solver.termination_condition in [
                TerminationCondition.maxTimeLimit]

            self.solver.options[self.timeLimit] = self.solver.options[self.timeLimit] - \
                self.solver._last_solve_time
            if(self.solver.options[self.timeLimit] <= 0):
                fail = True
                break

            # if we hit the time limit, we keep track of the worst possible bound (i.e. the highest) in order to give an estimate about
            # how bad our solution can be, given that time limit was hit at least once
            if(MP_time_limit_hit):
                MPresultsAsString = str(self.MP_model.results)
                worstMPBoundCandidate = float(
                    re.search("Upper bound: -*(\d*.\d*)", MPresultsAsString).group(1))
                if(worstMPBoundCandidate > worstMPBoundTimeLimitHit):
                    worstMPBoundTimeLimitHit = worstMPBoundCandidate

            # SP
            total_SP_building_time += self.create_SP_instance(data)
            if(self.solver.options[self.timeLimit] <= 0):
                fail = True
                break

            self.fix_SP_x_variables()
            print("Solving SP instance...")
            self.SP_model.results = self.solver.solve(
                self.SP_instance, tee=True)
            print("SP instance solved.")
            solverTime += self.solver._last_solve_time
            SP_time_limit_hit = SP_time_limit_hit or self.SP_model.results.solver.termination_condition in [
                TerminationCondition.maxTimeLimit]

            self.solver.options[self.timeLimit] = self.solver.options[self.timeLimit] - \
                self.solver._last_solve_time

            # no solution found, but solver status is fine: need to add a cut
            if(self.SP_model.results.solver.termination_condition in [TerminationCondition.infeasibleOrUnbounded, TerminationCondition.infeasible, TerminationCondition.unbounded]):
                self.MP_instance.cuts.add(sum(
                    1 - self.MP_instance.x[i, k, t] for i in self.MP_instance.i for k in self.MP_instance.k for t in self.MP_instance.t if round(self.MP_instance.x[i, k, t].value) == 1) >= 1)
                print("Generated cuts so far: \n")
                self.MP_instance.cuts.display()
                print("\n")
            else:
                break

        status_ok = False
        if(not fail):
            status_ok = self.SP_model.results.solver.status == SolverStatus.ok
            objectiveValue = pyo.value(self.SP_instance.objective)

        run_info = {"solutionTime": solverTime,
                    "MPBuildingTime": MPBuildingTime,
                    "SP_building_time": total_SP_building_time,
                    "status_ok": status_ok,
                    "objectiveValue": objectiveValue,
                    "MP_time_limit_hit": MP_time_limit_hit,
                    "SP_time_limit_hit": SP_time_limit_hit,
                    "worstMPBoundTimeLimitHit": worstMPBoundTimeLimitHit,
                    "iterations": iterations,
                    "fail": fail}

        if(not fail):
            print(self.SP_model.results)
        return run_info
