import logging
from .module import Module

logger = logging.getLogger(__name__)


class Context:
    def __init__(self, modules: dict):
        self.registered_modules = modules

    def get_module(self, module_name: str):
        module = self.registered_modules.get(module_name)
        if not module:
            raise Exception(f"Module {module_name} not registered")

        return module

    def start(self):
        for module in self.registered_modules.values():
            logger.info("Starting module %s", module.get_name())
            module: Module = module
            module.start(self)

