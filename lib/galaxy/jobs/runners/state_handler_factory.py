import logging

from galaxy.util.submodules import submodules

import galaxy.jobs.runners.state_handlers


log = logging.getLogger(__name__)


def build_state_handlers():
    return _get_state_handlers_dict()


def _get_state_handlers_dict():
    state_handlers = {}
    for module in submodules(galaxy.jobs.runners.state_handlers):
        for func in module.__all__:
            if func not in state_handlers:
                state_handlers[func] = []
            state_handlers[func].append(getattr(module, func))
            log.debug("Loaded '%s' state handler from module %s", func, module.__name__)
    return state_handlers
