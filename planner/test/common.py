import unittest
from data_maker import DataDescriptor, DataMaker


def build_data_dictionary():
    data_descriptor = DataDescriptor(patients = 60,
                                    days = 5,
                                    anesthetists = 2,
                                    infection_frequency = 0.5,
                                    anesthesia_frequency = 0.5,
                                    robustness_parameter=2)

    dataMaker = DataMaker(seed=52876, data_descriptor=data_descriptor)
    return dataMaker.create_data_dictionary()


class TestCommon(unittest.TestCase):

    def non_empty_solution(self):
        operated = 0
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        for k in range(1, K + 1):
            for t in range(1, T + 1):
                operated = operated + len(self.solution[(k, t)])
        self.assertTrue(operated > 0)

    def non_overlapping_patients(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        for k in range(1, K + 1):
            for t in range(1, T + 1):
                patients = self.solution[(k, t)]
                patientsNumber = len(patients)
                if(patientsNumber == 0):
                    continue
                for i1 in range(0, patientsNumber):
                    for i2 in range(0, patientsNumber):
                        if(i1 != i2):
                            self.assertTrue((patients[i1].order + patients[i1].operatingTime + patients[i1].arrival_delay <= patients[i2].order or patients[i2].order + patients[i2].operatingTime + patients[i2].arrival_delay <= patients[i1].order)
                                            and not (patients[i1].order + patients[i1].operatingTime + patients[i1].arrival_delay <= patients[i2].order and patients[i2].order + patients[i2].operatingTime + patients[i2].arrival_delay <= patients[i1].order))

    def non_overlapping_anesthetists(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        for t in range(1, T + 1):
            for k1 in range(1, K + 1):
                for k2 in range(1, K + 1):
                    if(k1 == k2):
                        continue
                    k1Patients = self.solution[(k1, t)]
                    k1PatientsNumber = len(k1Patients)
                    k2Patients = self.solution[(k2, t)]
                    k2PatientsNumber = len(k2Patients)
                    if(k1PatientsNumber == 0 or k2PatientsNumber == 0):
                        continue
                    for i1 in range(0, k1PatientsNumber):
                        for i2 in range(0, k2PatientsNumber):
                            if(k1Patients[i1].anesthetist and k2Patients[i2].anesthetist and k1Patients[i1].anesthetist == k2Patients[i2].anesthetist):
                                self.assertTrue((k1Patients[i1].order + k1Patients[i1].operatingTime + k1Patients[i1].arrival_delay <= k2Patients[i2].order or k2Patients[i2].order + k2Patients[i2].operatingTime + k2Patients[i2].arrival_delay <= k1Patients[i1].order)
                                 and not (k1Patients[i1].order + k1Patients[i1].operatingTime + k1Patients[i1].arrival_delay <= k2Patients[i2].order and k2Patients[i2].order + k2Patients[i2].operatingTime + k2Patients[i2].arrival_delay <= k1Patients[i1].order))

    def surgery_time_constraint(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        for k in range(1, K + 1):
            for t in range(1, T + 1):
                patients = self.solution[(k, t)]
                patientsNumber = len(patients)
                if(patientsNumber == 0):
                    continue
                totalOperatingTime = sum(map(lambda p: p.operatingTime, patients))
                total_delay_time = sum(map(lambda p: p.arrival_delay, patients))
                self.assertTrue(totalOperatingTime + total_delay_time <= self.dataDictionary[None]["s"][(k, t)])

    def end_of_day_constraint(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        for k in range(1, K + 1):
            for t in range(1, T + 1):
                patients = self.solution[(k, t)]
                patientsNumber = len(patients)
                if(patientsNumber == 0):
                    continue
                for i in range(0, patientsNumber):
                    self.assertTrue(patients[i].order + patients[i].operatingTime + patients[i].arrival_delay <= self.dataDictionary[None]["s"][(k, t)])

    def anesthesia_total_time_constraint(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        A = self.dataDictionary[None]["A"][None]
        for t in range(1, T + 1):
            patients = []
            for k in range(1, K + 1):
                patients.extend(self.solution[(k, t)])
            for a in range(1, A + 1):
                patientsWithAnesthetist = list(
                    filter(lambda p: p.anesthetist and p.anesthetist == a, patients))
                if(len(patientsWithAnesthetist) == 0):
                    continue
                surgery_time = sum(map(lambda p: p.operatingTime, patientsWithAnesthetist))
                arrival_delay_time = 0
                for patient in patientsWithAnesthetist:
                    if patient.delay:
                        arrival_delay_time += patient.arrival_delay

                self.assertTrue(surgery_time + arrival_delay_time <= self.dataDictionary[None]["An"][(a, t)])

    def single_surgery(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        patients = []
        for k in range(1, K + 1):
            for t in range(1, T + 1):
                patients.extend(self.solution[(k, t)])
        patientIds = list(map(lambda p : p.id, patients))
        self.assertTrue(len(patientIds) == len(set(patientIds)))

    def anesthetist_assignment(self):
        K = self.dataDictionary[None]["K"][None]
        T = self.dataDictionary[None]["T"][None]
        for k in range(1, K + 1):
            for t in range(1, T + 1):
                for patient in self.solution[(k, t)]:
                    if(patient.anesthesia == 1):
                        self.assertTrue(patient.anesthetist > 0)
                    else:
                        self.assertTrue(patient.anesthetist == 0)