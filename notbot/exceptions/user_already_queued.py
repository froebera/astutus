from .notbot_exception import NotbotException


class UserAlreadyQueued(NotbotException):
    def __init__(self, queued_index: int):
        self.queued_index = queued_index
