import unittest

from test.common import build_data_dictionary
from test.common import TestCommon
from planners import FastCompleteHeuristicPlanner, FastCompleteLagrangeanHeuristicPlanner


class TestFCEStandard(TestCommon):

    @classmethod
    def setUpClass(self):
        self.dataDictionary = build_data_dictionary()
        planner = FastCompleteHeuristicPlanner(timeLimit=900, gap=0.01, solver="cplex")
        planner.solve_model(self.dataDictionary)
        self.solution = planner.extract_solution()

    def test_non_empty_solution(self):
        self.non_empty_solution()

    def test_non_overlapping_patients(self):
        self.non_overlapping_patients()

    def test_non_overlapping_anesthetists(self):
        self.non_overlapping_anesthetists()

    def test_priority_constraints(self):
        self.priority_constraints()

    def test_surgery_time_constraint(self):
        self.surgery_time_constraint()

    def test_end_of_day_constraint(self):
        self.end_of_day_constraint()

    def test_anesthesia_total_time_constraint(self):
        self.anesthesia_total_time_constraint()

    def test_single_surgery(self):
        self.single_surgery()

    def test_anesthetist_assignment(self):
        self.anesthetist_assignment()


class TestFCEVariant(TestCommon):

    @classmethod
    def setUpClass(self):
        self.dataDictionary = build_data_dictionary()
        planner = FastCompleteLagrangeanHeuristicPlanner(timeLimit=900, gap=0.01, solver="cplex")
        planner.solve_model(self.dataDictionary)
        self.solution = planner.extract_solution()

    def test_non_empty_solution(self):
        self.non_empty_solution()

    def test_non_overlapping_patients(self):
        self.non_overlapping_patients()

    def test_non_overlapping_anesthetists(self):
        self.non_overlapping_anesthetists()

    def test_priority_constraints(self):
        self.priority_constraints()

    def test_surgery_time_constraint(self):
        self.surgery_time_constraint()

    def test_end_of_day_constraint(self):
        self.end_of_day_constraint()

    def test_anesthesia_total_time_constraint(self):
        self.anesthesia_total_time_constraint()

    def test_single_surgery(self):
        self.single_surgery()

    def test_anesthetist_assignment(self):
        self.anesthetist_assignment()


if __name__ == '__main__':
    unittest.main()
