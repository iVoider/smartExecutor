
# support FDG-guided execution and sequence execution
from fdg.FunctionCoverage import FunctionCoverage
from fdg.deepFunctionSelection import DeepFunctionSelection
from fdg.instructionModification import InstructionModification
from fdg.sequenceAndState import SequenceAndState
from fdg.sequenceExecutionControl import SequenceExecutionControl
from copy import copy, deepcopy

from fdg.FDG import FDG
from fdg.contractInfo import ContractInfo
from fdg.sequenceGeneration import SequenceGeneration
from mythril.laser.ethereum.svm import LaserEVM
from mythril.laser.plugin.interface import LaserPlugin
from mythril.laser.plugin.builder import PluginBuilder
from mythril.laser.plugin.plugins.coverage import coverage_plugin, InstructionCoveragePlugin
from mythril.laser.plugin.plugins.dependency_pruner import get_dependency_annotation, \
     get_ftn_seq_annotation_from_ws

from mythril.laser.ethereum.state.global_state import GlobalState
from mythril.laser.ethereum.transaction.transaction_models import (
    ContractCreationTransaction,
)

import logging
import fdg.FDG_global


log = logging.getLogger(__name__)


global contract_ddress
contract_address=0x0


class FDG_prunerBuilder(PluginBuilder):
    name = "fdg-pruner"
    def __call__(self, *args, **kwargs):
        return FDG_pruner(**kwargs)


class FDG_pruner(LaserPlugin):
    """ """
    def __init__(self,instructionCoveragePlugin:InstructionCoveragePlugin):
        """Creates FDG pruner"""
        self._reset()
        self.functionCoverage=FunctionCoverage(instructionCoveragePlugin,
                                               fdg.FDG_global.ftns_instr_indices,
                                               fdg.FDG_global.target_bytecode)

    def _reset(self):
        self._iteration_ = 0

        self.contract_info=None # save data resulted from Slither
        self.FDG=None
        self.sequenceAndState=None
        self.instructionModification=None
        self.deepFtnSelection=None
        self.sequenceGeneration=None
        self.seqExeControl = None

        # tempararily save sequences for the current iteration
        self.save_cur_iteration_all_sequences = []  # all sequences in the current iteration
        self.save_cur_iteration_state_change_sequences = []  # all valid sequences in the current iteration

        self.flag_phase2_start = False
        self.flag_phase2_termination=False


    def initialize(self, symbolic_vm: LaserEVM) -> None:
        """Initializes the FDG_pruner
        :param symbolic_vm
        """
        self._reset()

        @symbolic_vm.laser_hook("start_sym_exec")
        def start_sym_exec_hook():
            # get contract data
            self.contract_info=ContractInfo(fdg.FDG_global.solidity_path, fdg.FDG_global.contract,fdg.FDG_global.method_identifiers)
            self.functionCoverage.set_index_to_ftn_pure_name(self.contract_info.ftn_to_idx)

            # create an FDG
            self.FDG=FDG(self.contract_info,level_phase1=fdg.FDG_global.level_phase1,level_phase2=fdg.FDG_global.level_phase2)

            # for saving the generated states and executed sequences
            self.sequenceAndState=SequenceAndState(self.contract_info,self.functionCoverage)

            self.instructionModification=InstructionModification(self.contract_info)

            self.deepFtnSelection=DeepFunctionSelection(self.FDG,self.sequenceAndState)

            self.sequenceGeneration=SequenceGeneration(self.FDG,self.sequenceAndState)

            self.seqExeControl = SequenceExecutionControl(self.sequenceAndState,self.functionCoverage)

        @symbolic_vm.laser_hook("stop_sym_exec")
        def stop_sym_exec_hook():
            # make sure deep functions are not checked in phase 1.
            deep_functions_1st_time = self.functionCoverage.get_deep_functions_1st_time()
            if len(deep_functions_1st_time) > 0:
                print(f'@@WEI:go_through_sequence_generation')



        @symbolic_vm.laser_hook("start_sym_trans_laserEVM")
        def start_sym_trans_hook_laserEVM(laserEVM: LaserEVM):
            """
            ...
            add states to laserEVM.open_states so that they can be used
            as base states in the next iteration of symbolic transaction
            :param laserEVM: instance of LaserEVM
            :return:
            """
            self._iteration_ += 1

            if self._iteration_ == 1:
                self.instructionModification.feed_instructions(laserEVM, contract_address)

            if fdg.FDG_global.phase1_execute_all_sequences == 1:
                # execute all sequences, thus does not need to identify childrens in phase 1
                return

            # specify the functions to be executed on each open states(world states)
            if self._iteration_ <=fdg.FDG_global.phase1_depth_limit and self._iteration_>1:
                modified_states=[]
                for idx,state in enumerate(laserEVM.open_states):
                    ftn_seq=get_ftn_seq_annotation_from_ws(state)
                    ftn_idx_seq=[]
                    for ftn_name in ftn_seq:
                        if ftn_name in self.contract_info.ftn_to_idx.keys():
                            ftn_idx_seq.append(self.contract_info.get_index_from_name(ftn_name))
                        else:
                            ftn_idx_seq.append(ftn_name) # functions of state variables (future work)

                    # get children nodes
                    children=[]
                    if not isinstance(ftn_idx_seq[-1],int): #means functions of state variables #to-do-list
                        sv=str(ftn_idx_seq[-1]).split("(")[0]
                        children=self.FDG.get_ftn_read_SV(sv,fdg.FDG_global.level_phase1) # in phase 1, so, the level is 0 by default
                    else:
                        children = self.FDG.get_children(ftn_idx_seq[-1])
                    if len(children)>0:
                        children_selectors=[self.contract_info.get_selector_from_index(idx) for idx in children]

                        # modify function dispatcher so that only specified functions are executed
                        modified_state=deepcopy(state)
                        self.instructionModification.modify_instructions_on_one_state(modified_state, children_selectors)
                        modified_states.append(modified_state)

                # update the open states so that the states having no children nodes are removed
                laserEVM.open_states=modified_states

        @symbolic_vm.laser_hook("stop_sym_trans_laserEVM")
        def stop_sym_trans_hook_laserEVM(laserEVM: LaserEVM):
            """
            - save states
            - some saved states are used as initial states in sequence execution

            :param laserEVM:
            :return:
            """
            # print(f'end: self._iteration_={self._iteration_}')
            if self._iteration_ == 0: return

            # save states and their corresponding sequences
            old_states_count = len(laserEVM.open_states)
            self.open_states = [
                state for state in laserEVM.open_states if state.constraints.is_possible
            ]
            prune_count = old_states_count - len(laserEVM.open_states)
            if prune_count:log.info("Pruned {} unreachable states".format(prune_count))

            for state in laserEVM.open_states:
                ftn_seq=self.sequenceAndState.save_state_and_its_sequence(state)

            # check the code coverage for each function
            if self._iteration_==fdg.FDG_global.phase1_depth_limit:
                self.functionCoverage.compute_coverage()

                if fdg.FDG_global.phase2_include!=1:
                    # terminate
                    fdg.FDG_global.transaction_count = self._iteration_
                    laserEVM.open_states = []
                    return

            if self.flag_phase2_start:
                self.seqExeControl.end_exe_a_function()

            # signal to start sequence execution
            if self._iteration_==fdg.FDG_global.phase1_depth_limit:
                self.flag_phase2_start=True
                laserEVM.open_states=[]

            # sequence execution
            if self.flag_phase2_start:
                # generate the sequences to be executed
                while self.seqExeControl.flag_to_generate_sequences:
                    deep_functions =self.functionCoverage.compute_deep_functions()
                    if len(deep_functions)==0:
                        self.flag_phase2_termination=True
                        break
                    # deep_function_selected =self.deepFtnSelection.select_a_deep_function_simple(deep_functions)
                    deep_function_selected = self.deepFtnSelection.select_a_deep_function(deep_functions)

                    if deep_function_selected==-1: # the deep function has no parent; thus no sequence can be generated
                        self.flag_phase2_termination = True
                        break
                    # generate sequences for the selected deep function
                    sequences =self.sequenceGeneration.generate_sequences(deep_function_selected)
                    if len(sequences) > 0:
                        self.seqExeControl.feed_generated_sequences(sequences,deep_function_selected)


                # terminate sequence execution
                if self.flag_phase2_termination:
                    # all deep functions are selected once
                    fdg.FDG_global.transaction_count = self._iteration_
                    laserEVM.open_states = []
                    return

                if not self.seqExeControl.flag_to_generate_sequences:
                    key, ftn_idx_to_be_executed = self.seqExeControl.start_exe_a_function()
                    if key is not None:
                        laserEVM.open_states = deepcopy(self.sequenceAndState.get_state(key))
                    # execute the function
                    if ftn_idx_to_be_executed is not None:
                        # # save the sequence that will be executed in this iteration

                        # modify the instructions of the states so that only the specified function is executed
                        # as one sequence is executed at one time, on all open states, the same function is executed.
                        ftn_selector = self.contract_info.get_selector_from_index(ftn_idx_to_be_executed)
                        self.instructionModification.modify_instructions_on_multiple_states(laserEVM.open_states, [ftn_selector])

        @symbolic_vm.laser_hook("add_world_state")
        def world_state_filter_hook(state: GlobalState):
            if isinstance(state.current_transaction, ContractCreationTransaction):
                # Reset iteration variable
                self._iteration_ = 0
                return

    def _print_sequences(self,nested_sequences):
        for seq in nested_sequences:
            ftn_name_seq=[]
            if seq is None:continue
            for ftn_idx in seq:
                if isinstance(ftn_idx,int):
                    ftn_name_seq.append(self.contract_info.get_name_from_index(ftn_idx))
                else:
                    ftn_name_seq.append(ftn_idx)
            print(ftn_name_seq)
