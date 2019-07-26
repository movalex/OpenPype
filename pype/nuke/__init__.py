import os
import sys

from avalon import api as avalon
from avalon.tools import workfiles
from pyblish import api as pyblish

from .. import api

from pype.nuke import menu
import logging

from .lib import (
    create_write_node
)

import nuke

from pypeapp import Logger

# #removing logger handler created in avalon_core
# for name, handler in [(handler.get_name(), handler)
#                       for handler in Logger.logging.root.handlers[:]]:
#     if "pype" not in str(name).lower():
#         Logger.logging.root.removeHandler(handler)
from . import lib


self = sys.modules[__name__]
self.workfiles_launched = False
log = Logger().get_logger(__name__, "nuke")

AVALON_CONFIG = os.getenv("AVALON_CONFIG", "pype")

PARENT_DIR = os.path.dirname(__file__)
PACKAGE_DIR = os.path.dirname(PARENT_DIR)
PLUGINS_DIR = os.path.join(PACKAGE_DIR, "plugins")

PUBLISH_PATH = os.path.join(PLUGINS_DIR, "nuke", "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "nuke", "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "nuke", "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "nuke", "inventory")


# registering pyblish gui regarding settings in presets
if os.getenv("PYBLISH_GUI", None):
    pyblish.register_gui(os.getenv("PYBLISH_GUI", None))


class NukeHandler(logging.Handler):
    '''
    Nuke Handler - emits logs into nuke's script editor.
    warning will emit nuke.warning()
    critical and fatal would popup msg dialog to alert of the error.
    '''

    def __init__(self):
        logging.Handler.__init__(self)
        self.set_name("Pype_Nuke_Handler")

    def emit(self, record):
        # Formated message:
        msg = self.format(record)

        if record.levelname.lower() in [
            # "warning",
            "critical",
            "fatal",
            "error"
        ]:
            msg = self.format(record)
            nuke.message(msg)


'''Adding Nuke Logging Handler'''
nuke_handler = NukeHandler()
if nuke_handler.get_name() \
    not in [handler.get_name()
            for handler in logging.root.handlers[:]]:
    logging.getLogger().addHandler(nuke_handler)
    logging.getLogger().setLevel(logging.INFO)


def reload_config():
    """Attempt to reload pipeline at run-time.

    CAUTION: This is primarily for development and debugging purposes.

    """

    import importlib

    for module in (
        "app",
        "app.api",
        "{}.api".format(AVALON_CONFIG),
        "{}.templates".format(AVALON_CONFIG),
        "{}.nuke.actions".format(AVALON_CONFIG),
        "{}.nuke.templates".format(AVALON_CONFIG),
        "{}.nuke.menu".format(AVALON_CONFIG),
        "{}.nuke.lib".format(AVALON_CONFIG),
    ):
        log.info("Reloading module: {}...".format(module))
        try:
            module = importlib.import_module(module)
            reload(module)
        except Exception as e:
            log.warning("Cannot reload module: {}".format(e))
            importlib.reload(module)


def install():

    # api.set_avalon_workdir()
    # reload_config()

    log.info("Registering Nuke plug-ins..")
    pyblish.register_plugin_path(PUBLISH_PATH)
    avalon.register_plugin_path(avalon.Loader, LOAD_PATH)
    avalon.register_plugin_path(avalon.Creator, CREATE_PATH)
    avalon.register_plugin_path(avalon.InventoryAction, INVENTORY_PATH)

    pyblish.register_callback("instanceToggled", on_pyblish_instance_toggled)

    # Disable all families except for the ones we explicitly want to see
    family_states = [
        "write",
        "review"
    ]

    avalon.data["familiesStateDefault"] = False
    avalon.data["familiesStateToggled"] = family_states

    menu.install()

    # Workfiles.
    launch_workfiles = os.environ.get("WORKFILES_STARTUP")

    if launch_workfiles:
        nuke.addOnCreate(launch_workfiles_app, nodeClass="Root")

    # Set context settings.
    nuke.addOnCreate(lib.set_context_settings, nodeClass="Root")


def launch_workfiles_app():
    if not self.workfiles_launched:
        self.workfiles_launched = True
        workfiles.show(os.environ["AVALON_WORKDIR"])


def uninstall():
    log.info("Deregistering Nuke plug-ins..")
    pyblish.deregister_plugin_path(PUBLISH_PATH)
    avalon.deregister_plugin_path(avalon.Loader, LOAD_PATH)
    avalon.deregister_plugin_path(avalon.Creator, CREATE_PATH)

    pyblish.deregister_callback("instanceToggled", on_pyblish_instance_toggled)


def on_pyblish_instance_toggled(instance, old_value, new_value):
    """Toggle node passthrough states on instance toggles."""
    log.info("instance toggle: {}, old_value: {}, new_value:{} ".format(
        instance, old_value, new_value))

    from avalon.nuke import (
        viewer_update_and_undo_stop,
        add_publish_knob
    )

    # Whether instances should be passthrough based on new value

    with viewer_update_and_undo_stop():
        n = instance[0]
        try:
            n["publish"].value()
        except ValueError:
            n = add_publish_knob(n)
            log.info(" `Publish` knob was added to write node..")

        n["publish"].setValue(new_value)
