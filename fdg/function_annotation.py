from copy import copy

from virtualenv.config.convert import NoneType




from mythril.laser.ethereum.svm import LaserEVM
from mythril.laser.plugin.interface import LaserPlugin
from mythril.laser.plugin.builder import PluginBuilder
from mythril.laser.plugin.plugins.dependency_pruner import get_dependency_annotation
from mythril.laser.plugin.signals import PluginSkipState

from mythril.laser.ethereum.state.global_state import GlobalState
from mythril.laser.ethereum.transaction.transaction_models import (
    ContractCreationTransaction,
)


from mythril.laser.plugin.plugins.plugin_annotations import (
    FunctionAnnotation,
    WSFunctionAnnotation,
)

from typing import cast, List, Dict, Set
import logging
import fdg.FDG_global
import time
import numpy as np
log = logging.getLogger(__name__)


def get_function_annotation(state: GlobalState) -> FunctionAnnotation:
    """ Returns a function annotation

    :param state: A global state object
    """

    annotations = cast(
        List[FunctionAnnotation], list(state.get_annotations(FunctionAnnotation))
    )

    if len(annotations) == 0:

        """FIXME: Hack for carrying over state annotations from the STOP and RETURN states of
        the previous states. The states are pushed on a stack in the world state annotation
        and popped off the stack in the subsequent iteration. This might break if any
        other strategy than bfs is used (?).
        """

        try:
            world_state_annotation = get_ws_function_annotation(state)
            annotation = world_state_annotation.annotations_stack.pop()
        except IndexError:
            annotation = FunctionAnnotation()

        state.annotate(annotation)
    else:
        annotation = annotations[0]

    return annotation

def get_ws_function_annotation(state: GlobalState) -> WSFunctionAnnotation:
    """ Returns the world state annotation

    :param state: A global state object
    """

    annotations = cast(
        List[WSFunctionAnnotation],
        list(state.world_state.get_annotations(WSFunctionAnnotation)),
    )

    if len(annotations) == 0:
        annotation = WSFunctionAnnotation()
        state.world_state.annotate(annotation)
    else:
        annotation = annotations[0]

    return annotation


class ftn_annotationBuilder(PluginBuilder):
    name = "fdg-pruner"

    def __call__(self, *args, **kwargs):
        return ftn_annotation()

class ftn_annotation(LaserPlugin):
    """ """

    def __init__(self):
        """Creates FDG pruner"""
        self._reset()


    def _reset(self):
        self._iteration_ = 0


    def initialize(self, symbolic_vm: LaserEVM) -> None:
        """Initializes the FDG_pruner
        :param symbolic_vm
        """
        self._reset()

        @symbolic_vm.laser_hook("start_sym_exec")
        def start_sym_exec_hook():
           pass

        @symbolic_vm.laser_hook("stop_sym_exec")
        def stop_sym_exec_hook():
            print(f' end of symbolic execution')
            pass

        @symbolic_vm.laser_hook("start_sym_trans")
        def start_sym_trans_hook():
            self._iteration_+=1


        @symbolic_vm.pre_hook("STOP")
        def stop_hook(state: GlobalState):
            _transaction_end(state)

        @symbolic_vm.pre_hook("RETURN")
        def return_hook(state: GlobalState):
            _transaction_end(state)

        def _transaction_end(state: GlobalState) -> None:
            """
            - collect function pairs that the second function is executed with return or stop
            - function pair: (fa,fb), fb depends on fa. fa provides states as initial states for executing fb.
                if fb is executed without revert, fb depends on fa; otherwise, fb does not.

            :param state:
            """
            annotation = get_function_annotation(state)
            annotation.function_seq.append(state.environment.active_function_name)



        @symbolic_vm.laser_hook("add_world_state")
        def world_state_filter_hook(state: GlobalState):
            if isinstance(state.current_transaction, ContractCreationTransaction):
                # Reset iteration variable
                self._iteration_ = 0
                return

            world_state_annotation = get_ws_function_annotation(state)
            annotation = get_function_annotation(state)
            world_state_annotation.annotations_stack.append(annotation)


