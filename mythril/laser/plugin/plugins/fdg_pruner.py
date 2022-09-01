
# support FDG-guided execution and sequence execution

from copy import copy
from fdg import utils
from fdg.FDG import FDG
from fdg.funtion_info import Function_info
from fdg.sequence import Sequence
from mythril.laser.ethereum.svm import LaserEVM
from mythril.laser.plugin.interface import LaserPlugin
from mythril.laser.plugin.builder import PluginBuilder
from mythril.laser.plugin.plugins.coverage import coverage_plugin
from mythril.laser.plugin.plugins.dependency_pruner import get_dependency_annotation
from mythril.laser.plugin.signals import PluginSkipState
from mythril.laser.ethereum.state.global_state import GlobalState
from mythril.laser.ethereum.transaction.transaction_models import (
    ContractCreationTransaction,
)
from mythril.laser.plugin.plugins.plugin_annotations import WSDependencyAnnotation, DependencyAnnotation
import logging
import fdg.FDG_global
import time
import numpy as np

log = logging.getLogger(__name__)


class FDG_prunerBuilder(PluginBuilder):
    name = "fdg-pruner"

    def __call__(self, *args, **kwargs):
        return FDG_pruner()


class FDG_pruner(LaserPlugin):
    """ """

    def __init__(self):
        """Creates FDG pruner"""
        self._reset()

    def _reset(self):

        self._iteration_ = 0
        self.solidity = ''
        self.contract = ''
        self.FDG = None
        self.function_mark = []  # used to record if a function is assigned or the execution of it succeeds at depth 1
        self.fdg_pc = {}  # assign chilren function entry PCs to each function used in FDG-guided execution phase

        # used to control the execution flow
        self.all_pc_list = {}
        self.selector_pc = {}
        self.ftn_pc = {}
        self.pc_ftn = {}
        self.pc_control_interval = {}
        self.gt_pc = []
        self.valid_pc_interval = []

        # save data during in FDG-guided execution phase
        self.OS_states = {}  # save in-between transaction states
        self.executed_ftn_pc = {}  # save executed ftn_pc sequences
        self.sequences = {}  # save vailid sequencess
        self.saved_open_states={}
        self.uncovered_functions = []
        self.uncovered_functions_pc_list = []
        self.ftn_special_pc = []
        self.uncovered_leaf_nodes_wo_DD_edges = []
        self.ftn_unable_to_assign = []

        # coverage related
        self.ftn_instructions_coverage_info = {}
        self.ftn_instructions_indices = {}
        self.ftn_identifiers = {}
        self.instruction_list = []

        # sequence related
        self.seq_object = None


        self.flag_no_sequence_generated_handle = False
        self.flag_no_sequence_generated_handle_start = False
        self.ftn_no_sequences_pc_list = []
        self.ftn_special_pc=[]
        self.ftn_special_pc__no_sequence_pc_combined=[]

        self.states_available=[]
        self.states_available_depth=0
        self.states_available_depth_index=0
        
        self.flag_sequence_handle=False
        self.cur_sequence=[]
        self.cur_sequence_pc = []
        self.cur_sequence_depth=0
        self.cur_sequence_depth_index=0

        self.saved_open_states_sequence_execution_phase={}
        self.flag_go_through_sequence_generation=False
        


    def initialize(self, symbolic_vm: LaserEVM) -> None:
        """Initializes the FDG_pruner
        :param symbolic_vm
        """
        self._reset()

        @symbolic_vm.laser_hook("start_sym_exec")
        def start_sym_exec_hook():
            # initialize FDG
            self.solidity = fdg.FDG_global.solidity_path
            self.contract = fdg.FDG_global.contract
            # build FDG
            function_info = Function_info(self.solidity, self.contract)
            self.FDG = FDG(function_info.functions_dict_slither())

            self.function_mark = [False] * self.FDG.num_ftn
            if len(self.function_mark) > 2:
                self.function_mark[0] = True
                self.function_mark[1] = True
            for ftn_idx in self.FDG.nodes_wo_DD_edges:
                self.function_mark[ftn_idx] = True
            self.uncovered_leaf_nodes_wo_DD_edges = self.FDG.nodes_wo_DD_edges

            self.ftn_instructions_indices = fdg.FDG_global.ftns_instr_indices
            for ftn_full_name, identifier in fdg.FDG_global.method_identifiers.items():
                # remve '(...)' from function signature,
                # use pure name as key because self.ftn_instructions_indices uses only pure name as key
                self.ftn_identifiers[str(ftn_full_name).split('(')[0]] = identifier

            for ftn, ftn_instr_list in fdg.FDG_global.ftns_instr_indices.items():
                # if ftn=='constructor' or ftn=='fallback':continue
                if ftn == 'constructor': continue
                self.ftn_instructions_coverage_info[ftn] = [0 / len(ftn_instr_list), ftn_instr_list]

        @symbolic_vm.laser_hook("stop_sym_exec")
        def stop_sym_exec_hook():
            if self.flag_go_through_sequence_generation:
                print(f'@@WEI:go_through_sequence_generation')
            if self.seq_object:
                print(f'generated sequences:{self.seq_object.sequences_generated}')
            if fdg.FDG_global.print_ftn_coverage==1:
                print(f'End of symbolic execution')
                for ftn, ftn_cov in self.ftn_instructions_coverage_info.items():
                    print("{:.2f}% coverage for {}".format(ftn_cov[0], ftn))

            # # check the code coverage for each function
            # instr_cov_record_list = fdg.FDG_global.ftns_instr_cov
            # if len(instr_cov_record_list)>0:
            #     instr_array = np.array(instr_cov_record_list)
            #     for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
            #         if ftn_instr_cov[0] == 100: continue
            #         status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
            #         opcodes=self.instruction_list[fdg.FDG_global.ftns_instr_indices[ftn]]
            #         opcode_idx_not_covered=list(np.invert(status))
            #         opcodes_not_covered=opcodes[opcode_idx_not_covered]
            #         print(f'{ftn},not covered: {opcodes_not_covered}')
            #         if ftn=='mint':
            #             print(f'mint: opcodes:{opcodes}')
            #         if ftn == 'transferFrom':
            #             print(f'transferFrom: opcodes:{opcodes}')
            # all_instr_idx_not_covered=list(np.invert(instr_array))
            # all_instr_not_covered=self.instruction_list[all_instr_idx_not_covered]
            # print(f'contract: not covered:{all_instr_not_covered}')


        @symbolic_vm.laser_hook("stop_sym_trans")
        def execute_stop_sym_trans_hook():
            # ----------------------------
            if self._iteration_ == 1:
                # extract valid pc interval
                if len(self.gt_pc) > 0:
                    self.valid_pc_interval = utils.get_valid_pc_interval(self.gt_pc,
                                                                         self.pc_control_interval[
                                                                             'pc_interval_end'])
                # map function index to its pc
                for ftn_i in range(2, self.FDG.num_ftn):  # constructor and fallback do not have selector
                    selector = self.FDG.index_to_selector[ftn_i]
                    if selector in self.selector_pc.keys():
                        self.ftn_pc[ftn_i] = self.selector_pc[selector]
                        self.pc_ftn[self.selector_pc[selector]] = ftn_i

                # map fallback function to the max pc in pc_control_interval
                if 'pc_interval_end' in self.pc_control_interval.keys():
                    self.ftn_pc[1]=self.pc_control_interval['pc_interval_end']
                    self.pc_ftn[self.pc_control_interval['pc_interval_end']]=1

                # prepare data for graph-based execution phase
                for prt,children in self.FDG.graph.items():
                    children_pc=[self.ftn_pc[ftn_idx] for ftn_idx in children if ftn_idx in self.ftn_pc.keys()]
                    self.fdg_pc[prt]=sorted(children_pc)



        # -------------------------------------------------
        ''' 
          new hook methods for changing laserEVM instance
        - add states 
        - save states        
        '''

        # -------------------------------------------------
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

            # ========================================================
            # start to sequence execution phase
            if self.flag_sequence_handle:
                if not self.seq_object:
                    # empty the initial states
                    laserEVM.open_states = []
                    # create an Sequence object
                    self.seq_object = Sequence(self.FDG, self.uncovered_functions, list(self.saved_open_states.keys()),
                                               fdg.FDG_global.depth_all_ftns_reached,fdg.FDG_global.seq_num_limit)
                    self._request_next_sequence(laserEVM)
                    if self.cur_sequence_depth>0: # indicate that the execution enters the phase of sequence execution
                        self.flag_go_through_sequence_generation=True
                else:
                    if self.cur_sequence_depth_index==self.cur_sequence_depth-1 and self.cur_sequence_depth>0:
                        # check if the target function covered or not, if yes, request the next sequence
                        if self.cur_sequence[-1] not in self.uncovered_functions: # targe function is covered
                            if len(self.uncovered_functions)>0:
                                # only add valid sequences from the phase of sequence execution
                                self.seq_object.valid_sequences_given =list(self.saved_open_states_sequence_execution_phase.keys())
                                self._request_next_sequence(laserEVM)
                            else:
                                # end sequence execution
                                self.flag_sequence_handle=False
                                self.flag_no_sequence_generated_handle=True

                        else: # continue execute the sequence on next state
                            if self.states_available_depth_index==self.states_available_depth-1: # all states are considered
                                # request next sequence
                                # only add valid sequences from the phase of sequence execution
                                self.seq_object.valid_sequences_given = list(self.saved_open_states_sequence_execution_phase.keys())
                                self._request_next_sequence(laserEVM)
                            else:
                                # execute the same sequence on the next available state
                                self.states_available_depth_index+=1
                                self.cur_sequence_depth_index=self.cur_sequence_start_index
                                laserEVM.open_states=[copy(self.states_available[self.states_available_depth_index])]

                    else: # continue to execute the sequence
                        self.cur_sequence_depth_index+=1

            # =======================================================
            # handle uncovered functions that have no sequence generated or special functions
            if self.flag_no_sequence_generated_handle:
                # the first time to handle special or uncovered functions:
                if not self.flag_no_sequence_generated_handle_start:
                    self.flag_no_sequence_generated_handle_start=True
                    # get functions that no sequences are generated for
                    if len(self.ftn_no_sequences_pc_list)==0:
                        self.ftn_no_sequences_pc_list = [self.ftn_pc[ftn_idx] for ftn_idx in
                                                         self.seq_object.ftn_no_sequences if
                                                         ftn_idx in self.ftn_pc.keys()]
                    self.ftn_special_pc__no_sequence_pc_combined = self.ftn_no_sequences_pc_list + self.ftn_special_pc
                    self.ftn_special_pc__no_sequence_pc_combined.sort()

                    if len(self.ftn_special_pc__no_sequence_pc_combined)==0:
                        self.flag_no_sequence_generated_handle=False
                        fdg.FDG_global.transaction_count = self._iteration_
                        return
                    # get states from saved states
                    self.states_available = []
                    keys = list(self.saved_open_states.keys()) + list(
                        self.saved_open_states_sequence_execution_phase.keys())
                    for key in keys:
                        state_list = []
                        if key not in self.saved_open_states.keys():
                            state_list = self.saved_open_states_sequence_execution_phase[key]
                        else:
                            state_list = self.saved_open_states[key]
                        for state in state_list:
                            self.states_available.append(state)

                    self.states_available_depth = len(self.states_available)
                    if self.states_available_depth == 0:  # exit special function handle
                        self.flag_no_sequence_generated_handle = False
                        fdg.FDG_global.transaction_count = self._iteration_
                        return
                    else:laserEVM.open_states=[copy(self.states_available[self.states_available_depth_index])]
                else:

                    # not the fist time, check if all these functions covered and there are states left
                    if len(self.ftn_special_pc__no_sequence_pc_combined)>0:
                        if self.states_available_depth_index<self.states_available_depth-1:
                            # go to the next states
                            self.states_available_depth_index+=1
                            laserEVM.open_states = [copy(self.states_available[self.states_available_depth_index])]
                            return
                    # end
                    self.flag_no_sequence_generated_handle = False
                    fdg.FDG_global.transaction_count = self._iteration_






        @symbolic_vm.laser_hook("stop_sym_trans_laserEVM")
        def stop_sym_trans_hook_laserEVM(laserEVM: LaserEVM):
            """
            - save states
            - only need to states from depth 1 to fdg.FDG_global.depth_all_ftns_reached+1
            - some saved states are used as initial states in sequence execution

            :param laserEVM:
            :return:
            """
            if self._iteration_ == 0: return

            # ----------------------------
            # save states
            if self._iteration_ <= fdg.FDG_global.depth_all_ftns_reached:
                self._save_states(laserEVM,True)
            elif self.flag_sequence_handle:
                if self.cur_sequence_depth_index == self.cur_sequence_depth - 1:
                    self._save_states(laserEVM,False)

            # to avoid ending the first phase too quickly(at depth 1 when there are functions not covered)(no data dependency in FDG)
            if self._iteration_==1:
                self._update_coverage()

            # ----------------------------
            # compute the depth (<=4)
            self._compute_depth_1_phase()

            # ----------------------------
            # # prepare initial states for the next transaction in graph-based execution phase
            if self._iteration_ < fdg.FDG_global.depth_all_ftns_reached:
                # prepare initial states for the next transaction
                open_states=[]
                for key,value in self.saved_open_states.items():
                    ftn_seq=str(key).split(',')
                    if len(ftn_seq)==self._iteration_:
                        prt_idx=int(ftn_seq[-1])
                        flag_remove = False
                        if prt_idx not in self.fdg_pc.keys():
                            flag_remove = True
                        elif len(self.fdg_pc[prt_idx]) == 0:
                            flag_remove = True
                        if prt_idx == 1:  # do not remove states when the state is from a fallback
                            flag_remove = False
                        if not flag_remove:
                            for state in value:
                                open_states.append(copy(state))
                laserEVM.open_states = open_states


            # ----------------------------
            # at the end of graph-based execution phase
            if self._iteration_==fdg.FDG_global.depth_all_ftns_reached:
                # check the code coverage for each function
                self._update_coverage()

                # get and update uncovered special functions
                self._get_or_update_uncovered_functions_pc()

                # if all functions covered, stop,otherwise, go the sequence execution phase
                if len(self.uncovered_functions) == 0 and len(self.ftn_special_pc) == 0:
                    # set to the current iteration, so that execution engine can stop
                    fdg.FDG_global.transaction_count = self._iteration_
                    return
                else:
                    self.flag_sequence_handle = True


            # ----------------------------
            # sequence-oriented execution phase
            if self.flag_sequence_handle:
                if self.cur_sequence_depth_index==self.cur_sequence_depth-1 and self.cur_sequence_depth_index>=1:
                    # update coverage to get uncovered functions
                    self._update_coverage()


            # ----------------------------
            # handle "special" functions:
            # not able to execute in graph-based execution phase,
            # functions that no sequences are generated
            if self.flag_no_sequence_generated_handle:
                # update coverage to get uncovered functions
                self._update_coverage()
                # update self.ftn_special_pc__no_sequence_pc_combined
                # get uncovered "special" functions
                uncovered_ftn_pc=[self.ftn_pc[ftn] for ftn in self.uncovered_functions if ftn in self.ftn_pc.keys()]
                self.ftn_special_pc__no_sequence_pc_combined=[pc for pc in self.ftn_special_pc__no_sequence_pc_combined if pc in set(uncovered_ftn_pc).union(set(self.ftn_special_pc))]
                self.ftn_special_pc__no_sequence_pc_combined.sort()






        ''' 
             changing machine state PC to PCs associated to specified functions at depth >1
        '''

        # -------------------------------------------------

        @symbolic_vm.post_hook("DUP1")
        def dup1_hook(state: GlobalState):
            if self._iteration_ >= 2:

                # only consider DUP1 within a specified range
                pc_here = state.mstate.pc
                if len(self.selector_pc) == 0:
                    return
                if len(self.gt_pc) == 0:
                    if pc_here < self.pc_control_interval['pc_interval_start']: return
                    if pc_here > self.pc_control_interval['pc_interval_end']: return
                else:
                    if not utils.pc_is_valid(pc_here, self.valid_pc_interval):
                        return

                # get the index of function, execution of which generates the state used as initial state in this transaction
                annotations = get_dependency_annotation(state)
                ftn_seq = annotations.ftn_seq
                if len(ftn_seq) == 0: return



                if self._iteration_ <= fdg.FDG_global.depth_all_ftns_reached:

                    parent = ftn_seq[-1]  # get the function name
                    parent_idx = -1

                    if parent not in self.FDG.ftn_to_index.keys():
                        if str(parent).__contains__('('):
                            parent = str(parent).split('(')[0]
                        if parent in self.FDG.ftn_0_to_index.keys():
                            parent_idx = self.FDG.ftn_0_to_index[parent]
                    else:
                        parent_idx = self.FDG.ftn_to_index[parent]

                    # prepare a list of PCs of functions to be assigned

                    if parent_idx == -1:  # functions do not in FDG, but change states
                        print(f'function {parent} does not in FDG, but changes states at iteration {self._iteration_ - 1}')
                        return

                    pc_list = self.fdg_pc[parent_idx] if parent_idx in self.fdg_pc.keys() else []
                    # assign pc
                    state.mstate.pc = utils.assign_pc_fdg_phase_dup1(state.mstate.pc, pc_list,
                                                      self.pc_control_interval)

                else:
                    executed_pc=[] # to avoid assigning pcs, the associated functions have been executed
                    # sequence execution phase
                    if self.flag_sequence_handle:
                        pc_list=[]
                        if self.cur_sequence_depth_index<len(self.cur_sequence_pc):
                             pc_list= [self.cur_sequence_pc[self.cur_sequence_depth_index]]

                        # assign pc
                        state.mstate.pc = utils.assign_pc_special_ftn_dup1(state.mstate.pc, pc_list, executed_pc,
                                                                           self.pc_control_interval)

                    # sequence execution phase
                    if self.flag_no_sequence_generated_handle:
                        pc_list = self.ftn_special_pc__no_sequence_pc_combined
                        # assign pc
                        state.mstate.pc = utils.assign_pc_special_ftn_dup1(state.mstate.pc, pc_list,
                                                                           executed_pc,
                                                                               self.pc_control_interval)

        # -------------------------------------------------
        ''' 
             save PC for each callable function at depth 1
        '''

        # -------------------------------------------------

        @symbolic_vm.pre_hook("PUSH4")
        def push4_hook(state: GlobalState):
            if self._iteration_ == 1:
                # if len(self.instruction_list) == 0:
                #     self.instruction_list = np.array(state.environment.code.instruction_list)

                # assume that self.pc_control_interval is extracted
                if 'pc_interval_start' not in self.pc_control_interval.keys():
                    return
                if state.mstate.pc < self.pc_control_interval['pc_interval_start']:
                    return
                if 'pc_interval_end' in self.pc_control_interval.keys():
                    if state.mstate.pc > self.pc_control_interval['pc_interval_end']:
                        return
                ftn_selector = state.instruction['argument'][2:]
                if ftn_selector not in self.selector_pc.keys():
                    self.selector_pc[ftn_selector] = state.mstate.pc

        # -------------------------------------------------
        ''' 
             capture the correct PC interval at depth 1 that dispatcher matches functions
        '''

        # -------------------------------------------------

        @symbolic_vm.pre_hook("GT")
        def gt_hook(state: GlobalState):
            # get the pc of jumpdest, the start opcode of a block meaning the end of function mapping

            if self._iteration_ == 1:
                if state.mstate.pc < self.pc_control_interval['pc_interval_start']:
                    return
                if 'pc_interval_end' in self.pc_control_interval.keys():
                    if state.mstate.pc > self.pc_control_interval['pc_interval_end']:
                        return

                self.gt_pc.append(state.mstate.pc)

        @symbolic_vm.pre_hook("CALLDATALOAD")
        def calldataload_hook(state: GlobalState):
            '''
            get the start pc for the valid pc interval
            '''
            if self._iteration_ == 1:
                if 'pc_interval_start' not in self.pc_control_interval.keys():
                    self.pc_control_interval['pc_interval_start'] = state.mstate.pc

        @symbolic_vm.pre_hook("CALLDATASIZE")
        def calldatasize_hook(state: GlobalState):
            if self._iteration_ == 1:
                if 'pc_signal_start' not in self.pc_control_interval.keys():
                    self.pc_control_interval['pc_signal_start'] = state.mstate.pc

        @symbolic_vm.pre_hook("JUMPDEST")
        def jumpdest_hook(state: GlobalState):
            '''
            get the maximum pc for the valid pc interval
            '''
            # pc should larger than self.pc_control_interval['pc_interval_start']
            # assume that the first occurance of jumpdest is the entry point for block of revert or fallback function

            if self._iteration_ == 1 and 'pc_signal_start' in self.pc_control_interval.keys() and 'pc_interval_end' not in self.pc_control_interval.keys():
                self.pc_control_interval['pc_interval_end'] = state.mstate.pc

        # -------------------------------------------------
        ''' 
             check states at the end of transactions to see to which function it belongs
        '''

        # -------------------------------------------------

        #
        # @symbolic_vm.pre_hook("RETURN")
        # def return_hook(state: GlobalState):
        #     # print(f'iteration={self._iteration_}')
        #     # print(f' hooked at return!')
        #     _transaction_end(state)
        #     # _print_state_info(state)
        #
        # @symbolic_vm.pre_hook("STOP")
        # def stop_hook(state: GlobalState):
        #     # print(f'iteration={self._iteration_}')
        #     # print(f' hooked at stop!')
        #     _transaction_end(state)
        #
        #
        # def _transaction_end(state: GlobalState) -> None:
        #     """
        #     save function sequences
        #     :param state:
        #     """
        #     # get valid sequences from states
        #     if self._iteration_ >=1 and self._iteration_ <= fdg.FDG_global.depth_all_ftns_reached\
        #         or self.cur_sequence_depth_index>=1 and self.cur_sequence_depth_index==self.cur_sequence_depth-1:
        #
        #         seq=_get_valid_sequence_from_state(state)
        #         if len(seq)>=1:
        #             if seq[-1] in self.sequences.keys():
        #                 if seq not in self.sequences[seq[-1]]:
        #                     self.sequences[seq[-1]] += [seq]
        #             else:
        #                 self.sequences[seq[-1]] = [seq]
        #
        # def _get_valid_sequence_from_state(state: GlobalState):
        #     """
        #     get valid sequences from global states
        #     :param state:
        #     """
        #     ftn_seq = get_dependency_annotation(state).ftn_seq
        #     ftn_idx_seq = []
        #     for ftn_full_name in ftn_seq:
        #         if ftn_full_name in self.FDG.ftn_to_index.keys():
        #             ftn_idx_seq.append(self.FDG.ftn_to_index[ftn_full_name])
        #         else:
        #             ftn_pure_name = ftn_full_name
        #             if str(ftn_full_name).count('('):
        #                 ftn_pure_name = str(ftn_full_name).split('(')[0]
        #             if ftn_pure_name in self.FDG.ftn_0_to_index.keys():
        #                 ftn_idx_seq.append(self.FDG.ftn_0_to_index[ftn_pure_name])
        #     return ftn_idx_seq

        # def _print_state_info(state:GlobalState)->None:
        #     print(f'==== constraints ====')
        #     for constraint in state.world_state.constraints:
        #         print(f'\t {constraint}')
        #     print(f'==== state.environment.active_account ====')
        #     print(f'\t {state.environment.active_account.address}')
        #
        #     print(f'==== storage of the active_account ====')
        #     for key, value in state.environment.active_account.storage.printable_storage.items():
        #         print(f'\t key {key}  value {value}')
        #
        #     print(f'==== memory ====')
        #     mem_size = state.mstate.memory_size
        #     for i in range(int(mem_size / 32)):
        #         word = state.mstate.memory.get_word_at(i)
        #         print(f'\t {word}')
        #     print(f'==== stack ====')
        #     for item in state.mstate.stack:
        #         print(f'\t {item}')


        @symbolic_vm.laser_hook("add_world_state")
        def world_state_filter_hook(state: GlobalState):
            if isinstance(state.current_transaction, ContractCreationTransaction):
                # Reset iteration variable
                self._iteration_ = 0
                return


    def _request_next_sequence(self, laserEVM: LaserEVM):
        while (True):
            self.cur_sequence = self.seq_object.get_one_sequence(self.uncovered_functions)
            print(f'execute sequence={self.cur_sequence}')
            if len(self.cur_sequence) < 2:  # the generated sequence has length >=2
                # signal the end of sequence execution
                self.flag_sequence_handle = False
                self.flag_no_sequence_generated_handle = True

                break
            else:
                self.cur_sequence_depth = len(self.cur_sequence)
                # locate the states
                key_to_state = str(self.cur_sequence[0])
                self.cur_sequence_depth_index = 1
                self.cur_sequence_start_index = 1
                for ftn in self.cur_sequence[1:]:
                    if key_to_state + "," + str(ftn) not in set(self.saved_open_states.keys()).union(set(self.saved_open_states_sequence_execution_phase.keys())):
                        break
                    else:
                        key_to_state += "," + str(ftn)
                        self.cur_sequence_depth_index += 1
                        self.cur_sequence_start_index += 1

                if self.cur_sequence_start_index<=self.cur_sequence_depth-1: # some functions in the sequence are not executed

                    # get states for the sequence
                    if key_to_state in self.saved_open_states.keys():
                        self.states_available = self.saved_open_states[key_to_state]
                    else:
                        self.states_available = self.saved_open_states_sequence_execution_phase[key_to_state]
                    self.states_available_depth = len(self.states_available)
                    self.states_available_depth_index = 0

                    if self.states_available_depth > 0:
                        # get pc for each function in the sequence
                        self.cur_sequence_pc = [0]
                        for i in range(1, self.cur_sequence_depth):
                            ftn_idx = self.cur_sequence[i]
                            if ftn_idx in self.ftn_pc.keys():
                                pc = self.ftn_pc[ftn_idx]
                                self.cur_sequence_pc.append(pc)
                        if self.states_available_depth_index < self.states_available_depth:
                            laserEVM.open_states = [copy(self.states_available[self.states_available_depth_index])]
                        break

    def _update_coverage(self):
        """
        update coverage and get uncovered functions
        :return:
        """
        instr_cov_record_list = fdg.FDG_global.ftns_instr_cov # get from coverage plugin through a global variable
        if len(instr_cov_record_list) > 0:
            instr_array = np.array(instr_cov_record_list)
            self.uncovered_functions = []
            self.ftn_special_pc = []
            for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
                if ftn_instr_cov[0] == 100: continue
                status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
                cov_instr = sum(status)
                cov = cov_instr / float(len(status)) * 100
                self.ftn_instructions_coverage_info[ftn] = [cov, status]
                if cov < 98:
                    # functions of public state variables can not be in FDG
                    if ftn in self.FDG.ftn_0_to_index.keys():
                        self.uncovered_functions.append(self.FDG.ftn_0_to_index[ftn])
                    else:
                        # FDG is empty
                        # or public functions of state variables, not in FDG.
                        # if len(self.FDG.nodes)==0: # we do not consider function of state variables
                        identifier = self.ftn_identifiers[ftn] if ftn in self.ftn_identifiers.keys() else '0000000'
                        ftn_pc = self.selector_pc[identifier] if identifier in self.selector_pc.keys() else \
                            self.pc_control_interval['pc_interval_end']
                        self.ftn_special_pc.append(ftn_pc)

    def _get_or_update_uncovered_functions_pc(self):
        """
        get uncovered functions that are not able to be assigned in the first phase (no edge, or too deep)
        these functions are handled separately after the sequence execution

        :return:
        """

        temp = []
        for ftn_idx in self.uncovered_leaf_nodes_wo_DD_edges:
            if ftn_idx in self.uncovered_functions:
                temp.append(ftn_idx)
        self.uncovered_leaf_nodes_wo_DD_edges = temp

        temp1 = []
        for ftn_idx in self.ftn_unable_to_assign:
            if ftn_idx in self.uncovered_functions:
                temp1.append(ftn_idx)
        self.ftn_unable_to_assign = temp1

        ftns = temp + temp1
        ftns_pc = [self.ftn_pc[ftn_idx] for ftn_idx in ftns if ftn_idx in self.ftn_pc.keys()]

        # add those uncovered public functions of state variables
        self.ftn_special_pc += ftns_pc
        self.ftn_special_pc = list(set(self.ftn_special_pc))
        self.ftn_special_pc.sort()


    def _save_states(self, laserEVM: LaserEVM, flag_save_states_1_phase: bool):
        for state in laserEVM.open_states:
            if not state.constraints.is_possible: continue
            ftn_name = state.node.function_name
            stop = False
            ftn_seq = []
            for annotation in state.annotations:
                if isinstance(annotation, WSDependencyAnnotation):
                    for anno in annotation.annotations_stack:
                        if isinstance(anno, DependencyAnnotation):
                            ftn_seq = anno.ftn_seq
                            stop = True
                            break
                    if stop:
                        break
            # get the function index sequence
            if len(ftn_seq) > 0:
                ftn_idx_seq = []
                for ftn_full_name in ftn_seq:
                    if ftn_full_name in self.FDG.ftn_to_index.keys():
                        ftn_idx_seq.append(self.FDG.ftn_to_index[ftn_full_name])
                    else:
                        ftn_pure_name = ftn_full_name
                        if str(ftn_full_name).count('('):
                            ftn_pure_name = str(ftn_full_name).split('(')[0]
                        if ftn_pure_name in self.FDG.ftn_0_to_index.keys():
                            ftn_idx_seq.append(self.FDG.ftn_0_to_index[ftn_pure_name])

                # save with the sequence as key wile [state] as value
                key = str(ftn_idx_seq[0])
                for idx in range(1, len(ftn_idx_seq)):
                    key += "," + str(ftn_idx_seq[idx])
                if flag_save_states_1_phase:
                    # save states at FDG-guided execution phase
                    if key not in self.saved_open_states.keys():
                        self.saved_open_states[key] = [copy(state)]
                    else:
                        self.saved_open_states[key] += [copy(state)]
                else:
                    if key not in self.saved_open_states_sequence_execution_phase.keys():
                        self.saved_open_states_sequence_execution_phase[key] = [copy(state)]
                    else:
                        self.saved_open_states_sequence_execution_phase[key] += [copy(state)]

    def _compute_depth_1_phase(self):
        """
        compute the depth in the graph-based phase, i.e., the first phase
        the max depth is 5
        """
        if self._iteration_ <= 3:
            if not all(self.function_mark):
                ftn_list=[str(item).split(',') for item in self.saved_open_states.keys()]
                ftn_list=[item for item in ftn_list if len(item)==self._iteration_]
                ftn_list=[int(item) for item_list in ftn_list for item in item_list]
                reached_ftns=list(set(ftn_list))

                # mark all functions, the execution of which at depth 1 succeeds
                if self._iteration_ == 1:
                    for ftn_idx in reached_ftns:
                        self.function_mark[ftn_idx] = True
                # check one depth further
                children = [self.FDG.graph[ftn_idx] for ftn_idx in reached_ftns if ftn_idx in self.FDG.graph.keys()]
                children = [item for sublist in children for item in sublist]
                if len(children) == 0:
                    # assign all uncovered functions
                    self.function_mark = [True] * self.FDG.num_ftn
                    fdg.FDG_global.depth_all_ftns_reached = self._iteration_
                    self.FDG.depth_limit = self._iteration_
                else:
                    for child in set(children):
                        self.function_mark[child] = True
                    if all(self.function_mark):
                        fdg.FDG_global.depth_all_ftns_reached = self._iteration_ + 1
                        self.FDG.depth_limit = self._iteration_ + 1
                    else:
                        # if at depth 3, and there is no hope that at depth 4 all functions are marked
                        #
                        if self._iteration_ == 3:
                            self.ftn_unable_to_assign = [idx for idx in range(1, self.FDG.num_ftn) if
                                                         self.function_mark[idx] == False]
                            self.function_mark = [True] * self.FDG.num_ftn
                            fdg.FDG_global.depth_all_ftns_reached = self._iteration_ + 1
                            self.FDG.depth_limit = self._iteration_ + 1
            else:
                if self._iteration_==1:
                    if len(self.uncovered_functions)>0 or len(self.ftn_special_pc)>0:
                        fdg.FDG_global.depth_all_ftns_reached = self._iteration_ + 1
                        self.FDG.depth_limit =  self._iteration_ + 1
                else:
                    if fdg.FDG_global.depth_all_ftns_reached == 5:  # means that this value is not written before
                        fdg.FDG_global.depth_all_ftns_reached = self._iteration_
                        self.FDG.depth_limit = self._iteration_

