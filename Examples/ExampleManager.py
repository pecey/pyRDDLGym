import os
import re
from Core.ErrorHandling.RDDLException import RDDLEnvironmentNotExist, RDDLInstanceNotExist

EXP_DICT = {
    'Cartpole' : ('A simple continuous MDP for the classical cart-pole system by Rich Sutton.', '/Cartpole/', 'CartPole'),
    'Elevators' : ('The Elevator domain models evening rush hours when people from different floors in '
                   'a building want to go down to the bottom floor using elevators', '/Elevator/', 'Elevator'),
    'MarsRover' : ('Multi Rover Navigation, where a group of agent needs to harvest mineral.', '/Mars_rover/', 'MarsRover'),
    'Mountaincar' : ('A simple continuous MDP for the classical mountain car control problem.', '/Mountaincar/', 'MountainCar'),
    'Power generation' : ('A simple power generation problem loosely modeled on the problem of unit commitment.',
                          '/Power_gen/', 'PowerGen'),
    'RaceCar' : ('A simple continuous MDP for the racecar problem.', '/RaceCar/', 'Racecar'),
    'Recsim' : ('A problem of recommendation systems, with consumers and providers.', '/Recsim/', 'Text'),
    'UAV continuous' : ('Continous action space version of multi-UAV problem where a group of UAVs have to reach goal '
                        'positions in  in the 3d Space.', '/UAV/Continuous/', 'UAVs'),
    'UAV discrete' : ('Discrete action space version of multi-UAV problem where a group of UAVs have to reach goal '
    'positions in  in the 3d Space.', '/UAV/Discrete/', 'UAVs'),
    'UAV mixed' : ('Mixed action space version of multi-UAV problem where a group of UAVs have to reach goal '
    'positions in  in the 3d Space.', '/UAV/Mixed/', 'UAVs'),
    'Wildfire' : ('A boolean version of the wildfire fighting domain.', '/Wildfire/', 'Wildfire'),
}


# class RDDLEnvironmentNotExist(ValueError):
#     pass


class RDDLInstanceNotExist(ValueError):
    pass


class ExampleManager:
    def __init__(self, env: str):
        self.env = env
        if env not in EXP_DICT:
            raise RDDLEnvironmentNotExist("Environment {} does not exist".format(env)
                          + ExampleManager._print_stack_trace(env))

        self.path_to_env = os.path.dirname(os.path.abspath(__file__)) + EXP_DICT[env][1]

    def get_domain(self):
        domain = self.path_to_env + 'domain.rddl'
        return domain

    def list_instances(self):
        files = os.listdir(self.path_to_env)
        instances = []
        for file in files:
            x = re.search("instance\d+.*", file)
            if x is not None:
                instances.append(file)
        return instances

    def get_instance(self, num: int):
        instance = 'instance' + str(num)+ '.rddl'
        if not os.path.exists(self.path_to_env + instance):
            raise RDDLInstanceNotExist(
                "instance {} does not exist for example environment {}".format(instance, self.env) +
                ExampleManager._print_stack_trace(instance))
        return self.path_to_env + instance

    def get_visualizer(self):
        viz_package_name = 'Visualizer.' + EXP_DICT[self.env][2] + 'Viz'
        viz_class_name = EXP_DICT[self.env][2] + 'Visualizer'
        viz_package = __import__(viz_package_name, {}, {}, viz_class_name)
        viz = getattr(viz_package, viz_class_name)
        return viz

    @staticmethod
    def ListExamples():
        print("Available example environment:")
        for key in EXP_DICT:
            print(key + " -> " + EXP_DICT[key[0]])

    @staticmethod
    def GetEnvInfo(env):
        return ExampleManager(env)
        pass

    @staticmethod
    def _print_stack_trace(expr):
        return '...\n' + str(expr) + '\n...'