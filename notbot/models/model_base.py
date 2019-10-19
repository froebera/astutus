class ModelBase:
    def __str__(self):
        return "{}({})".format(
            type(self).__name__,
            ", ".join([f"{attr}: {value}" for attr, value in self.__dict__.items()]),
        )

    def __repr__(self):
        return "{}({})".format(
            type(self).__name__,
            ", ".join([f"{value}" for attr, value in self.__dict__.items()]),
        )
