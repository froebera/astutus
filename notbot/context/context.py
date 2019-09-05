import logging
from typing import Callable, Dict

from .module import Module

logger = logging.getLogger(__name__)


class Context:
    def __init__(self):
        # Contains the module creator functions
        self.module_list = []
        # Contains all registered and created modules, indexed by name
        self.module_map: Dict[Module] = {}
        self.initialized = False
        self.creationDepth = 0
        self._bot = None

        # for m in modules:
        #     self.registered_modules[m.get_name()] = m

    def set_bot(self, bot):
        self._bot = bot

    def get_bot(self):
        return self._bot

    def _maybe_get_module(self, name):
        module = self.module_map.get(name, None)
        return module

    def add_module(self, module: Module):
        if self.initialized:
            raise Exception(
                "Context has been initialized already. Can no longer add new modules"
            )
        module_name = module.get_name()

        if self.module_map.__contains__(module_name):
            raise Exception(f"Module {module_name} registered already")

        logger.info(
            "%sAdding module %s of class %s",
            " " * (3 * self.creationDepth),
            module_name,
            type(module).__name__,
        )
        self.module_map[module_name] = module

    def get_or_register_module(self, module_name, creator: Callable[[], Module]):
        logger.info(
            "%sRequesting module %s", " " * (3 * self.creationDepth), module_name
        )
        module = self._maybe_get_module(module_name)
        if not module:
            logger.info(
                "%sCreating module %s", " " * (3 * self.creationDepth), module_name
            )
            self.creationDepth = self.creationDepth + 1
            module = creator()
            self.creationDepth = self.creationDepth - 1

            self.add_module(module)

        return module

    def get_module(self, module_name):
        module = self._maybe_get_module(module_name)
        if not module:
            raise Exception(f"Module {module_name} is not registered")
        return module

    def with_module(self, creator):
        self.module_list.append(creator)
        return self

    def start(self):
        for creator in self.module_list:
            logger.info(
                "%sCreating module requested from %s",
                " " * (3 * self.creationDepth),
                creator,
            )
            self.creationDepth = self.creationDepth + 1
            managed = creator(self)
            self.creationDepth = self.creationDepth - 1
            self.add_module(managed)

        self.initialized = True

        for module in self.module_map.values():
            logger.info("Starting module %s", module.get_name())
            module.start()

