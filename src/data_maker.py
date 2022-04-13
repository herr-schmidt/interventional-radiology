from typing_extensions import Self
from venv import create
from xmlrpc.client import MAXINT
from scipy.stats import truncnorm
from scipy.stats import binom
import numpy as np

from model import Patient


class TruncatedNormalParameters:
    def __init__(self, low, high, mean, stdDev):
        self.low = low
        self.high = high
        self.mean = mean
        self.stdDev = stdDev


class DataDescriptor:
    """Used to define properties of the sample to be generated."""

    def __init__(self):
        self._patients = None
        self._specialties = 2
        self._operatingRooms = 4
        self._days = None
        self._anesthetists = None
        self._covidFrequence = None
        self._anesthesiaFrequence = None
        self._specialtyBalance = None
        self._operatingDayDuration = None
        self._anesthesiaTime = None
        self._operatingTimeDistribution = None
        self._priorityDistribution = None

    @property
    def patients(self):
        """Get number of patients."""
        return self._patients

    @patients.setter
    def patients(self, value):
        self._patients = value

    @property
    def specialties(self):
        """Get number of specialties."""
        return self._specialties

    @property
    def operatingRooms(self):
        """Get number of operating rooms."""
        return self._operatingRooms

    @property
    def days(self):
        """Get number of days in the planning horizon."""
        return self._days

    @days.setter
    def days(self, value):
        self._days = value

    @property
    def anesthetists(self):
        """Get number of anesthetists."""
        return self._anesthetists

    @anesthetists.setter
    def anesthetists(self, value):
        self._anesthetists = value

    @property
    def covidFrequence(self):
        """Get Covid infection frequency."""
        return self._covidFrequence

    @covidFrequence.setter
    def covidFrequence(self, value):
        self._covidFrequence = value

    @property
    def anesthesiaFrequence(self):
        """Get anesthesia need frequency."""
        return self._anesthesiaFrequence

    @anesthesiaFrequence.setter
    def anesthesiaFrequence(self, value):
        self._anesthesiaFrequence = value

    @property
    def specialtyBalance(self):
        """Get specialty balance."""
        return self._specialtyBalance

    @specialtyBalance.setter
    def specialtyBalance(self, value):
        self._specialtyBalance = value

    @property
    def operatingDayDuration(self):
        """Get operating day duration."""
        return self._operatingDayDuration

    @operatingDayDuration.setter
    def operatingDayDuration(self, value):
        self._operatingDayDuration = value

    @property
    def anesthesiaTime(self):
        """Get anesthesia time at disposal for each anesthetist."""
        return self._anesthesiaTime

    @anesthesiaTime.setter
    def anesthesiaTime(self, value):
        self._anesthesiaTime = value

    @property
    def operatingTimeDistribution(self):
        """Get parameters of the Truncated Normal Distribution for generating operating times."""
        return self._operatingTimeDistribution

    @operatingTimeDistribution.setter
    def operatingTimeDistribution(self, value):
        self._operatingTimeDistribution = value

    @property
    def priorityDistribution(self):
        """Get parameters of the Truncated Normal Distribution for generating priorities."""
        return self._priorityDistribution

    @priorityDistribution.setter
    def priorityDistribution(self, value):
        self._priorityDistribution = value

    def initialize(self, patients, days, anesthetists, covidFrequence, anesthesiaFrequence, specialtyBalance, operatingTimeDistribution, priorityDistribution):
        self.patients = patients
        self.days = days
        self.anesthetists = anesthetists
        self.covidFrequence = covidFrequence
        self.anesthesiaFrequence = anesthesiaFrequence
        self.specialtyBalance = specialtyBalance
        self.operatingTimeDistribution = operatingTimeDistribution
        self.priorityDistribution = priorityDistribution

    def __str__(self):
        return f'Patients:{self.patients:17}\nDays:{self.days:21}\nAnesthetists:{self.anesthetists:13}\nCovid frequence:{self.covidFrequence:10}\nAnesthesia frequence:{self.anesthesiaFrequence:5}\nSpecialty balance:{self.specialtyBalance:8}\n\
Distributions for operating times and priorities are Truncated Normal Distributions with parameters:\n\
\tOperating times:\n\
\t\tLow:{self.operatingTimeDistribution.low:20}\n\
\t\tHigh:{self.operatingTimeDistribution.high:19}\n\
\t\tMean:{self.operatingTimeDistribution.mean:19}\n\
\t\tStandard deviation:{self.operatingTimeDistribution.stdDev:5}\n\
\tPriorities:\n\
\t\tLow:{self.priorityDistribution.low:20}\n\
\t\tHigh:{self.priorityDistribution.high:19}\n\
\t\tMean:{self.priorityDistribution.mean:19}\n\
\t\tStandard deviation:{self.priorityDistribution.stdDev:5}'


class DataMaker:
    def __init__(self):
        pass

    def generate_truncnorm_sample(self, patients, lower, upper, mean, stdDev):
        a = (lower - mean) / stdDev
        b = (upper - mean) / stdDev
        truncatedNormal = truncnorm(a, b, loc=mean, scale=stdDev)
        sample = truncatedNormal.rvs(patients)
        return sample

    def generate_binomial_sample(self, patients, p, isSpecialty):
        sample = binom.rvs(1, p, size=patients)
        if(isSpecialty):
            sample = sample + 1
        return sample

    def create_dictionary_entry(self, sample, isTime):
        dict = {}
        for i in range(0, len(sample)):
            if(isTime):
                dict[(i + 1)] = int(sample[i]) - int(sample[i]) % 10
            else:
                dict[(i + 1)] = int(sample[i])
        return dict

    def create_room_timetable(self, K, T, operatingDayDuration):
        dict = {}
        for k in range(0, K):
            for t in range(0, T):
                dict[(k + 1, t + 1)] = operatingDayDuration
        return dict

    def create_anestethists_timetable(self, A, T, anesthesiaTime):
        dict = {}
        for a in range(0, A):
            for t in range(0, T):
                dict[(a + 1, t + 1)] = anesthesiaTime
        return dict

    def create_patient_specialty_table(self, I, J, specialtyLabels):
        dict = {}
        for i in range(0, I):
            for j in range(0, J):
                if(specialtyLabels[(i + 1)] == j + 1):
                    dict[(i + 1, j + 1)] = 1
                else:
                    dict[(i + 1, j + 1)] = 0
        return dict

    def create_room_specialty_assignment(self, J, K, T):
        dict = {}
        for j in range(0, J):
            for k in range(0, K):
                for t in range(0, T):
                    if((j + 1 == 1 and (k + 1 == 1 or k + 1 == 2)) or (j + 1 == 2 and (k + 1 == 3 or k + 1 == 4))):
                        dict[(j + 1, k + 1, t + 1)] = 1
                    else:
                        dict[(j + 1, k + 1, t + 1)] = 0
        return dict

    def generate_data(self, dataDescriptor: DataDescriptor, seed):
        np.random.seed(seed=seed)
        operatingRoomTimes = self.create_room_timetable(dataDescriptor.operatingRooms,
                                                        dataDescriptor.days,
                                                        dataDescriptor.operatingDayDuration)
        anesthetistsTimes = self.create_anestethists_timetable(dataDescriptor.anesthetists,
                                                               dataDescriptor.days,
                                                               dataDescriptor.anesthesiaTime)
        operatingTimes = self.generate_truncnorm_sample(dataDescriptor.patients,
                                                        dataDescriptor.operatingTimeDistribution.low,
                                                        dataDescriptor.operatingTimeDistribution.high,
                                                        dataDescriptor.operatingTimeDistribution.mean,
                                                        dataDescriptor.operatingTimeDistribution.stdDev)
        priorities = self.generate_truncnorm_sample(dataDescriptor.patients,
                                                    dataDescriptor.priorityDistribution.low,
                                                    dataDescriptor.priorityDistribution.high,
                                                    dataDescriptor.priorityDistribution.mean,
                                                    dataDescriptor.priorityDistribution.stdDev)
        anesthesiaFlags = self.generate_binomial_sample(dataDescriptor.patients,
                                                        dataDescriptor.anesthesiaFrequence,
                                                        isSpecialty=False)
        covidFlags = self.generate_binomial_sample(dataDescriptor.patients,
                                                   dataDescriptor.covidFrequence,
                                                   isSpecialty=False)
        specialties = self.generate_binomial_sample(dataDescriptor.patients,
                                                    dataDescriptor.specialtyBalance,
                                                    isSpecialty=True)
        specialtyLabels = self.create_dictionary_entry(specialties,
                                                       isTime=False)
        totalOperatingTime = sum(operatingTimes)
        return {
            None: {
                'I': {None: dataDescriptor.patients},
                'J': {None: dataDescriptor.specialties},
                'K': {None: dataDescriptor.operatingRooms},
                'T': {None: dataDescriptor.days},
                'A': {None: dataDescriptor.anesthetists},
                'M': {None: 7},
                's': operatingRoomTimes,
                'An': anesthetistsTimes,
                'tau': self.create_room_specialty_assignment(dataDescriptor.specialties, dataDescriptor.operatingRooms, dataDescriptor.days),
                'p': self.create_dictionary_entry(operatingTimes, isTime=True),
                'r': self.create_dictionary_entry(priorities, isTime=False),
                'a': self.create_dictionary_entry(anesthesiaFlags, isTime=False),
                'c': self.create_dictionary_entry(covidFlags, isTime=False),
                'specialty': specialtyLabels,
                'rho': self.create_patient_specialty_table(dataDescriptor.patients, dataDescriptor.specialties, specialtyLabels),
                'bigM': {
                    1: dataDescriptor.patients,
                    2: totalOperatingTime,
                    3: totalOperatingTime,
                    4: totalOperatingTime,
                    5: totalOperatingTime,
                    6: dataDescriptor.patients
                }
            }
        }

    def print_data(self, data):
        patientNumber = data[None]['I'][None]
        for i in range(0, patientNumber):
            id = i + 1
            priority = data[None]['r'][(i + 1)]
            specialty = data[None]['specialty'][(i + 1)]
            operatingTime = data[None]['p'][(i + 1)]
            covid = data[None]['c'][(i + 1)]
            anesthesia = data[None]['a'][(i + 1)]
            print(Patient(id=id,
                          priority=priority,
                          specialty=specialty,
                          operatingTime=operatingTime,
                          covid=covid,
                          anesthesia=anesthesia,
                          room="N/A",
                          day="N/A",
                          anesthetist="N/A",
                          order="N/A"
                          ))
