import abc


class Module(abc.ABC):
    @abc.abstractmethod
    def start(self, context):
        pass

    def get_name(self):
        pass
