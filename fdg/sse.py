# support FDG-guided execution and sequence execution

from copy import copy, deepcopy

import sha3


from mythril.laser.ethereum.state.world_state import WorldState
from mythril.laser.ethereum.svm import LaserEVM
from mythril.laser.plugin.interface import LaserPlugin
from mythril.laser.plugin.builder import PluginBuilder

from mythril.laser.plugin.plugins.dependency_pruner import get_dependency_annotation

from mythril.laser.ethereum.state.global_state import GlobalState
from mythril.laser.ethereum.transaction.transaction_models import (
    ContractCreationTransaction,
)

import logging
import fdg.FDG_global
import time
import numpy as np

log = logging.getLogger(__name__)
global contract_ddress
contract_address=0x0

class SSE_prunerBuilder(PluginBuilder):
    name = "sse-support sequence execution"

    def __call__(self, *args, **kwargs):
        return sse()


class sse(LaserPlugin):
    """ """

    def __init__(self):
        self._reset()

    def _reset(self):
        print(f'sequence={fdg.FDG_global.sequences}')
        self._iteration_ = 0
        self.solidity = ''
        self.contract = ''
        self.sequences=[]
        self.seq_index=0
        self.ftn_index=0
        self.current_sequence=[]
        self.open_states = {}
        self.valid_sequences = {}

        self.fct_hash_2_pc_in_dispatcher={}
        self.instr_list_original=[]
        self.instructions_dict={}

        # coverage related
        self.ftn_instructions_coverage_info = {}
        self.ftn_instructions_indices = {}
        self.ftn_identifiers = {}
        self.instruction_list = []



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


            # get sequences
            if fdg.FDG_global.sequences is not None:
                sequences=fdg.FDG_global.sequences.split(";")
                for seq in sequences:
                    seq_list=seq.split(",")
                    self.sequences.append(seq_list)

            if len(self.sequences) == 0:
                # # Crowdsale.sol
                # #[[invest(),setPhase(),withdraw()],[setPhase(),refund()]]
                # self.sequences = [['0xe8b5e51f', '0x2cc82655', '0x3ccfd60b'],['0x2cc82655','0x590e1ae3']]
                # # HoloToken.sol
                # #[[setMinter(),mint(),setDestroyer(),burn()]]
                # self.sequences = [['0xfca3b5aa', '0x40c10f19','0x6a7301b8','0x42966c68']]

                # # HoloToken.sol
                # # [[setDestroyer(),setMinter(),mint(),burn()]]
                # self.sequences = [['0x6a7301b8', '0xfca3b5aa', '0x40c10f19', '0x42966c68']]

                # # HoloToken.sol
                # # [[setMinter(),mint(),burn()]]
                # self.sequences = [['0xfca3b5aa', '0x40c10f19', '0x42966c68']]

                # HoloToken.sol
                # [[setDestroyer(),burn()]]
                self.sequences = [['0x6a7301b8', '0xfca3b5aa', '0x40c10f19', '0x42966c68'],['0x6a7301b8',  '0x42966c68']]

                # # HoloToken.sol
                # #[['setMinter(),mint(),mint()]]
                # self.sequences = [['0xfca3b5aa', '0x40c10f19', '0x40c10f19']]

                # # PDC_2.sol
                # #[[transfer_0()]]
                # self.sequences = [['0xc424ce6e']]

                # # PDC_2.sol
                # # [[transfer_1()]]
                # self.sequences = [['0xf9cbcc50']]
                # # PDC_2.sol
                # # [[transfer_2()]]
                # self.sequences = [['0xac44e240']]


                # # SMT.sol
                # # [['setExclude', 'transferProxy()']]
                # self.sequences = [['0x5f6f8b5f', '0xeb502d45']]
                # self.sequences = [['0xeb502d45']]

                # # Overflow.sol
                # # [['add']]
                # self.sequences = [['0x1003e2d2']]

                # # Overflow.sol
                # # [['safe_add', 'add']]
                # self.sequences =  [['0x3e127e76', '0x1003e2d2']]

                # #PDC_7.sol
                # #[['transfer_1()']]
                # self.sequences=[['0xf9cbcc50']]
                #
                # # PDC_7.sol
                # # [['transfer_2()']]
                # self.sequences = [['0x76afdf24']]




            self.ftn_instructions_indices = fdg.FDG_global.ftns_instr_indices
            for ftn_full_name, identifier in fdg.FDG_global.method_identifiers.items():
                # remove '(...)' from function signature,
                # use pure name as key because self.ftn_instructions_indices uses only pure name as key
                self.ftn_identifiers[str(ftn_full_name).split('(')[0]] = identifier

            for ftn, ftn_instr_list in fdg.FDG_global.ftns_instr_indices.items():
                # if ftn=='constructor' or ftn=='fallback':continue
                if ftn == 'constructor': continue
                self.ftn_instructions_coverage_info[ftn] = [0 / len(ftn_instr_list), ftn_instr_list]

        @symbolic_vm.laser_hook("stop_sym_exec")
        def stop_sym_exec_hook():
            # compute coverage
            instr_cov_record_list = fdg.FDG_global.ftns_instr_cov
            if len(instr_cov_record_list) > 0:
                instr_array = np.array(instr_cov_record_list)
                for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
                    if ftn_instr_cov[0] == 100: continue
                    status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
                    cov_instr = sum(status)
                    cov = cov_instr / float(len(status)) * 100
                    self.ftn_instructions_coverage_info[ftn] = [cov, status]


            if fdg.FDG_global.print_function_coverage == 1:
                print(f'End of symbolic execution')
                for ftn, ftn_cov in self.ftn_instructions_coverage_info.items():
                    print("{:.2f}% coverage for {}".format(ftn_cov[0], ftn))


        @symbolic_vm.laser_hook("stop_sym_trans")
        def execute_stop_sym_trans_hook():
            pass

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
            if self._iteration_==1:
                # collect the pc for each function hash in dispatcher
                self._collect_pc_for_fct_hashes_in_dispatcher(laserEVM)

            if len(self.current_sequence )==0:
                self.current_sequence=self.sequences[self.seq_index]

            # execute the sequence found
            new_states=[]
            for state in laserEVM.open_states:
                modity_state=deepcopy(state)
                self._modify_dispatcher_in_instruction_list(modity_state, [self.current_sequence[self.ftn_index]])
                new_states.append(deepcopy(modity_state))
            laserEVM.open_states=new_states
            self.ftn_index+=1

            print(f'iteration:{self._iteration_}')
            print(f'transaction_count:{fdg.FDG_global.transaction_count}')
            print(f'sequence index:{self.seq_index}')
            print(f'function index:{self.ftn_index}')





        @symbolic_vm.laser_hook("stop_sym_trans_laserEVM")
        def stop_sym_trans_hook_laserEVM(laserEVM: LaserEVM):
            """
            - save states

            :param laserEVM:
            :return:
            """
            if self.ftn_index >= len(self.current_sequence):
                self.seq_index += 1
                if self.seq_index >= len(self.sequences):
                    fdg.FDG_global.transaction_count = self._iteration_
                    return
                else:
                    self.current_sequence = self.sequences[self.seq_index]
                    self.ftn_index = 0
            # # ===================================================
            # # assumes all functions are executed at the depth 1
            # # ==================================================
            #
            # if self._iteration_==1:
            #     # collect the pc for each function hash in dispatcher
            #     self._collect_pc_for_fct_hashes_in_dispatcher(laserEVM)
            #
            #     # ----------------------------
            #     # save states
            #     self.open_states[self._iteration_]={}
            #     for state in laserEVM.open_states:
            #         if not state.constraints.is_possible: continue
            #         ftn_hash=self._get_function_selector(state.node.function_name)
            #         if  ftn_hash not in self.open_states[self._iteration_].keys():
            #             self.open_states[self._iteration_][ftn_hash]=[copy(state)]
            #         else:
            #             self.open_states[self._iteration_][ftn_hash] += [copy(state)]
            #
            #
            # # if len(self.current_sequence )==0:
            # #     self.current_sequence=self.sequences[self.seq_index]
            # # if self.ftn_index >= len(self.current_sequence) or self.ftn_index==0:
            # #     # find the sequence that the first function has been executed with new states generated.
            # #     while(True):
            # #         if self.seq_index>=len(self.sequences):
            # #             fdg.FDG_global.transaction_count=self._iteration_
            # #             break
            # #         self.current_sequence=self.sequences[self.seq_index]
            # #         if self.current_sequence[0] in self.open_states[1].keys():
            # #             self.seq_index+=1
            # #             modity_states = deepcopy(self.open_states[1][self.current_sequence[0]])
            # #             for state in modity_states:
            # #                 self._modify_dispatcher_in_instruction_list(state,[self.current_sequence[1]])
            # #                 laserEVM.open_states=[deepcopy(state)]
            # #             self.ftn_index=2
            # #
            # #             break
            # #         else:
            # #             self.seq_index+=1
            # #             continue
            # # else:
            # #     # execute the sequence found
            # #     new_states=[]
            # #     for state in laserEVM.open_states:
            # #         modity_state=deepcopy(state)
            # #         self._modify_dispatcher_in_instruction_list(modity_state, [self.current_sequence[self.ftn_index]])
            # #         new_states.append(deepcopy(modity_state))
            # #     laserEVM.open_states=new_states
            # #     self.ftn_index+=1

            # print(f'iteration:{self._iteration_}')
            # print(f'transaction_count:{fdg.FDG_global.transaction_count}')
            # print(f'sequence index:{self.seq_index}')
            # print(f'function index:{self.ftn_index}')



        # -------------------------------------------------
        '''
             check states at the end of transactions to see to which function it belongs
        '''

        # -------------------------------------------------

        @symbolic_vm.pre_hook("SHA3")
        def sload_hook(state: GlobalState):
            # print(f'iteration={self._iteration_}')
            # print(f' hooked at stop!')
            intr=state.instruction


        @symbolic_vm.pre_hook("STOP")
        def stop_hook(state: GlobalState):
            _transaction_end(state)

        @symbolic_vm.pre_hook("RETURN")
        def return_hook(state: GlobalState):
            _transaction_end(state)

        def _transaction_end(state: GlobalState) -> None:
            """
            save function sequences
            :param state:
            """

            # get valid sequences from states
            if self._iteration_ >1:
                seq = _get_valid_sequence_from_state(state)
                if len(seq) >= 1:
                    if seq[-1] in self.valid_sequences.keys():
                        if seq not in self.valid_sequences[seq[-1]]:
                            self.valid_sequences[seq[-1]] += [seq]
                    else:
                        self.valid_sequences[seq[-1]] = [seq]

        def _get_valid_sequence_from_state(state: GlobalState):
            """
            get valid sequences from global states
            :param state:
            """
            return get_dependency_annotation(state).ftn_seq





        @symbolic_vm.laser_hook("add_world_state")
        def world_state_filter_hook(state: GlobalState):
            if isinstance(state.current_transaction, ContractCreationTransaction):
                # Reset iteration variable
                self._iteration_ = 0
                return


    def _update_coverage(self):
        instr_cov_record_list = fdg.FDG_global.ftns_instr_cov
        if len(instr_cov_record_list) > 0:
            instr_array = np.array(instr_cov_record_list)

            for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
                if ftn_instr_cov[0] == 100: continue
                status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
                cov_instr = sum(status)
                cov = cov_instr / float(len(status)) * 100
                self.ftn_instructions_coverage_info[ftn] = [cov, status]


    def _modify_dispatcher_in_instruction_list(self, state: WorldState, fct_hashes: list):
        """
            remoeve the code in dispacher that direct the execution flow to functions in fct_hashes
        """

        remove_fct_hashes=[ftn_hash for ftn_hash in self.fct_hash_2_pc_in_dispatcher.keys() if ftn_hash not in fct_hashes]
        instr_offsets = [self.fct_hash_2_pc_in_dispatcher[signature] for signature in remove_fct_hashes]

        # Using lambda arguments: expression
        flatten_list = lambda irregular_list:[element for item in irregular_list for element in flatten_list(item)] if type(irregular_list) is list else [irregular_list]
        instr_offsets=flatten_list(instr_offsets)

        instr_offsets.sort()

        remove_instr_offsets = [offset for item in instr_offsets for offset in range(item, item + 5)]

        max_instr_offset = max(remove_instr_offsets)

        left_instructions = []
        offset = len(self.instructions_dict['prefix'])
        for instruction in self.instructions_dict['middle']:
            if not offset in remove_instr_offsets:
                left_instructions.append(instruction)
            else:
                left_instructions.append({"address": instruction["address"], "opcode": "EMPTY"})
            offset += 1

        len_mid=len(left_instructions)
        for i in range(len_mid):
            if left_instructions[len_mid-i-1]['opcode'].__eq__('EMPTY'):
                continue

            if left_instructions[len_mid-i-1]['opcode'].__eq__('DUP1'):
                left_instructions[len_mid-i-1]['opcode']="EMPTY"
            break



        modify_instructions= self.instructions_dict['prefix']+left_instructions+self.instructions_dict['suffix']

        state.accounts[contract_address.value].code.instruction_list = copy(modify_instructions)
        state.accounts[contract_address.value].code.func_hashes = fct_hashes

    def _collect_pc_for_fct_hashes_in_dispatcher(self, laserEVM:LaserEVM):
        """

        """
        if self._iteration_==1:
            stop_flag=False
            for state in laserEVM.open_states:
                if stop_flag:break # collect only from a state at depth 1
                stop_flag=True
                key = contract_address.value
                code=state.accounts[key].code
                instructions=code.instruction_list
                self.instruction_list=code.instruction_list
                fct_instr_offsets=[]


                function_hashes=code.func_hashes

                offset_instr=0
                for instruction in instructions:
                    opcode=instruction['opcode']
                    if str(opcode).__eq__('PUSH4'):
                        if instruction['argument'] in function_hashes:
                            if not str(instruction['argument']) in self.fct_hash_2_pc_in_dispatcher.keys():
                                self.fct_hash_2_pc_in_dispatcher[str(instruction['argument'])]=offset_instr
                            else:self.fct_hash_2_pc_in_dispatcher[str(instruction['argument'])]=[offset_instr]+[self.fct_hash_2_pc_in_dispatcher[str(instruction['argument'])]]
                            fct_instr_offsets.append(offset_instr)
                    offset_instr+=1
                    if len(self.fct_hash_2_pc_in_dispatcher)==len(function_hashes):
                        break
                # not yet consider the case of fallback functions
                min_offset=min(fct_instr_offsets)
                max_offst=max(fct_instr_offsets)
                self.instructions_dict['prefix']=instructions[0:min_offset]
                self.instructions_dict['middle'] = instructions[min_offset:max_offst+4]
                self.instructions_dict['suffix'] = instructions[max_offst+4:]

    def get_function_signature(self,sig: str) ->str:
        """'
            Return the function id of the given signature
        Args:
            sig (str)
        Return:
            (int)
        """
        s = sha3.keccak_256()
        s.update(sig.encode("utf-8"))
        return '0x'+s.hexdigest()[:8]




# #==========================================
# # all functions are executed at the depth 1
# # support FDG-guided execution and sequence execution
#
# from copy import copy, deepcopy
#
# import sha3
#
# from fdg import utils
# from fdg.FDG import FDG
# from fdg.funtion_info import Function_info
# from fdg.sequence import Sequence
# from mythril.laser.ethereum.state.world_state import WorldState
# from mythril.laser.ethereum.svm import LaserEVM
# from mythril.laser.plugin.interface import LaserPlugin
# from mythril.laser.plugin.builder import PluginBuilder
# from mythril.laser.plugin.plugins.coverage import coverage_plugin
# from mythril.laser.plugin.plugins.dependency_pruner import get_dependency_annotation
# from mythril.laser.plugin.signals import PluginSkipState
# from mythril.laser.ethereum.state.global_state import GlobalState
# from mythril.laser.ethereum.transaction.transaction_models import (
#     ContractCreationTransaction,
# )
#
# import logging
# import fdg.FDG_global
# import time
# import numpy as np
#
# log = logging.getLogger(__name__)
# global contract_ddress
# contract_address = 0x0
#
#
# class SSE_prunerBuilder(PluginBuilder):
#     name = "sse-support sequence execution"
#
#     def __call__(self, *args, **kwargs):
#         return sse()
#
#
# class sse(LaserPlugin):
#     """ """
#
#     def __init__(self):
#         self._reset()
#
#     def _reset(self):
#         print(f'sequence={fdg.FDG_global.sequences}')
#         self._iteration_ = 0
#         self.solidity = ''
#         self.contract = ''
#         self.sequences = []
#         self.seq_index = 0
#         self.ftn_index = 0
#         self.current_sequence = []
#         self.open_states = {}
#         self.valid_sequences = {}
#
#         self.fct_hash_2_pc_in_dispatcher = {}
#         self.instr_list_original = []
#         self.instructions_dict = {}
#
#         # coverage related
#         self.ftn_instructions_coverage_info = {}
#         self.ftn_instructions_indices = {}
#         self.ftn_identifiers = {}
#         self.instruction_list = []
#
#     def initialize(self, symbolic_vm: LaserEVM) -> None:
#         """Initializes the FDG_pruner
#         :param symbolic_vm
#         """
#         self._reset()
#
#         @symbolic_vm.laser_hook("start_sym_exec")
#         def start_sym_exec_hook():
#
#             # initialize FDG
#             self.solidity = fdg.FDG_global.solidity_path
#             self.contract = fdg.FDG_global.contract
#
#             # get sequences
#             if fdg.FDG_global.sequences is not None:
#                 sequences = fdg.FDG_global.sequences.split(";")
#                 for seq in sequences:
#                     seq_list = seq.split(",")
#                     self.sequences.append(seq_list)
#
#             if len(self.sequences) == 0:
#                 # # Crowdsale.sol
#                 # #[[invest(),setPhase(),withdraw()],[setPhase(),refund()]]
#                 # self.sequences = [['0xe8b5e51f', '0x2cc82655', '0x3ccfd60b'],['0x2cc82655','0x590e1ae3']]
#                 # # HoloToken.sol
#                 # self.sequences = [['0xfca3b5aa','0x40c10f19','0x40c10f19']]
#                 # HoloToken.sol
#                 # [['setMinter(),mint(),mint()]]
#                 self.sequences = [['0xfca3b5aa', '0x40c10f19', '0x40c10f19']]
#             self.ftn_instructions_indices = fdg.FDG_global.ftns_instr_indices
#             for ftn_full_name, identifier in fdg.FDG_global.method_identifiers.items():
#                 # remove '(...)' from function signature,
#                 # use pure name as key because self.ftn_instructions_indices uses only pure name as key
#                 self.ftn_identifiers[str(ftn_full_name).split('(')[0]] = identifier
#
#             for ftn, ftn_instr_list in fdg.FDG_global.ftns_instr_indices.items():
#                 # if ftn=='constructor' or ftn=='fallback':continue
#                 if ftn == 'constructor': continue
#                 self.ftn_instructions_coverage_info[ftn] = [0 / len(ftn_instr_list), ftn_instr_list]
#
#         @symbolic_vm.laser_hook("stop_sym_exec")
#         def stop_sym_exec_hook():
#             # compute coverage
#             instr_cov_record_list = fdg.FDG_global.ftns_instr_cov
#             if len(instr_cov_record_list) > 0:
#                 instr_array = np.array(instr_cov_record_list)
#                 for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
#                     if ftn_instr_cov[0] == 100: continue
#                     status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
#                     cov_instr = sum(status)
#                     cov = cov_instr / float(len(status)) * 100
#                     self.ftn_instructions_coverage_info[ftn] = [cov, status]
#
#             if fdg.FDG_global.print_ftn_coverage == 1:
#                 print(f'End of symbolic execution')
#                 for ftn, ftn_cov in self.ftn_instructions_coverage_info.items():
#                     print("{:.2f}% coverage for {}".format(ftn_cov[0], ftn))
#
#             # # check the code coverage for each function
#             # instr_cov_record_list = fdg.FDG_global.ftns_instr_cov
#             # if len(instr_cov_record_list)>0:
#             #     instr_array = np.array(instr_cov_record_list)
#             #     for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
#             #         if ftn_instr_cov[0] == 100: continue
#             #         status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
#             #         opcodes=self.instruction_list[fdg.FDG_global.ftns_instr_indices[ftn]]
#             #         opcode_idx_not_covered=list(np.invert(status))
#             #         opcodes_not_covered=opcodes[opcode_idx_not_covered]
#             #         print(f'{ftn},not covered: {opcodes_not_covered}')
#             #         if ftn=='mint':
#             #             print(f'mint: opcodes:{opcodes}')
#             #         if ftn == 'transferFrom':
#             #             print(f'transferFrom: opcodes:{opcodes}')
#             # all_instr_idx_not_covered=list(np.invert(instr_array))
#             # all_instr_not_covered=self.instruction_list[all_instr_idx_not_covered]
#             # print(f'contract: not covered:{all_instr_not_covered}')
#
#         @symbolic_vm.laser_hook("stop_sym_trans")
#         def execute_stop_sym_trans_hook():
#             pass
#
#         # -------------------------------------------------
#         '''
#           new hook methods for changing laserEVM instance
#         - add states
#         - save states
#         '''
#
#         # -------------------------------------------------
#         @symbolic_vm.laser_hook("start_sym_trans_laserEVM")
#         def start_sym_trans_hook_laserEVM(laserEVM: LaserEVM):
#             """
#             ...
#             add states to laserEVM.open_states so that they can be used
#             as base states in the next iteration of symbolic transaction
#             :param laserEVM: instance of LaserEVM
#             :return:
#             """
#             self._iteration_ += 1
#
#
#
#
#         @symbolic_vm.laser_hook("stop_sym_trans_laserEVM")
#         def stop_sym_trans_hook_laserEVM(laserEVM: LaserEVM):
#             """
#             - save states
#
#             :param laserEVM:
#             :return:
#             """
#
#             # ===================================================
#             # assumes all functions are executed at the depth 1
#             # ==================================================
#
#             if self._iteration_==1:
#                 # collect the pc for each function hash in dispatcher
#                 self._collect_pc_for_fct_hashes_in_dispatcher(laserEVM)
#
#                 # ----------------------------
#                 # save states
#                 self.open_states[self._iteration_]={}
#                 for state in laserEVM.open_states:
#                     if not state.constraints.is_possible: continue
#                     ftn_hash=self._get_function_selector(state.node.function_name)
#                     if  ftn_hash not in self.open_states[self._iteration_].keys():
#                         self.open_states[self._iteration_][ftn_hash]=[copy(state)]
#                     else:
#                         self.open_states[self._iteration_][ftn_hash] += [copy(state)]
#
#
#             if len(self.current_sequence )==0:
#                 self.current_sequence=self.sequences[self.seq_index]
#             if self.ftn_index >= len(self.current_sequence) or self.ftn_index==0:
#                 # find the sequence that the first function has been executed with new states generated.
#                 while(True):
#                     if self.seq_index>=len(self.sequences):
#                         fdg.FDG_global.transaction_count=self._iteration_
#                         break
#                     self.current_sequence=self.sequences[self.seq_index]
#                     if self.current_sequence[0] in self.open_states[1].keys():
#                         self.seq_index+=1
#                         modity_states = deepcopy(self.open_states[1][self.current_sequence[0]])
#                         for state in modity_states:
#                             self._modify_dispatcher_in_instruction_list(state,[self.current_sequence[1]])
#                             laserEVM.open_states=[deepcopy(state)]
#                         self.ftn_index=2
#
#                         break
#                     else:
#                         self.seq_index+=1
#                         continue
#             else:
#                 # execute the sequence found
#                 new_states=[]
#                 for state in laserEVM.open_states:
#                     modity_state=deepcopy(state)
#                     self._modify_dispatcher_in_instruction_list(modity_state, [self.current_sequence[self.ftn_index]])
#                     new_states.append(deepcopy(modity_state))
#                 laserEVM.open_states=new_states
#                 self.ftn_index+=1
#
#             print(f'iteration:{self._iteration_}')
#             print(f'transaction_count:{fdg.FDG_global.transaction_count}')
#             print(f'sequence index:{self.seq_index}')
#             print(f'function index:{self.ftn_index}')
#
#         # -------------------------------------------------
#         '''
#              check states at the end of transactions to see to which function it belongs
#         '''
#
#         # -------------------------------------------------
#
#         @symbolic_vm.pre_hook("STOP")
#         def stop_hook(state: GlobalState):
#             _transaction_end(state)
#
#         @symbolic_vm.pre_hook("RETURN")
#         def return_hook(state: GlobalState):
#             _transaction_end(state)
#
#         def _transaction_end(state: GlobalState) -> None:
#             """
#             save function sequences
#             :param state:
#             """
#
#             # get valid sequences from states
#             if self._iteration_ > 1:
#                 seq = _get_valid_sequence_from_state(state)
#                 if len(seq) >= 1:
#                     if seq[-1] in self.valid_sequences.keys():
#                         if seq not in self.valid_sequences[seq[-1]]:
#                             self.valid_sequences[seq[-1]] += [seq]
#                     else:
#                         self.valid_sequences[seq[-1]] = [seq]
#
#         def _get_valid_sequence_from_state(state: GlobalState):
#             """
#             get valid sequences from global states
#             :param state:
#             """
#             return get_dependency_annotation(state).ftn_seq
#
#         @symbolic_vm.laser_hook("add_world_state")
#         def world_state_filter_hook(state: GlobalState):
#             if isinstance(state.current_transaction, ContractCreationTransaction):
#                 # Reset iteration variable
#                 self._iteration_ = 0
#                 return
#
#     def _update_coverage(self):
#         instr_cov_record_list = fdg.FDG_global.ftns_instr_cov
#         if len(instr_cov_record_list) > 0:
#             instr_array = np.array(instr_cov_record_list)
#
#             for ftn, ftn_instr_cov in self.ftn_instructions_coverage_info.items():
#                 if ftn_instr_cov[0] == 100: continue
#                 status = instr_array[fdg.FDG_global.ftns_instr_indices[ftn]]
#                 cov_instr = sum(status)
#                 cov = cov_instr / float(len(status)) * 100
#                 self.ftn_instructions_coverage_info[ftn] = [cov, status]
#
#     def _modify_dispatcher_in_instruction_list(self, state: WorldState, fct_hashes: list):
#         """
#             remoeve the code in dispacher that direct the execution flow to functions in fct_hashes
#         """
#
#         remove_fct_hashes = [ftn_hash for ftn_hash in self.fct_hash_2_pc_in_dispatcher.keys() if
#                              ftn_hash not in fct_hashes]
#         instr_offsets = [self.fct_hash_2_pc_in_dispatcher[signature] for signature in remove_fct_hashes]
#
#         # Using lambda arguments: expression
#         flatten_list = lambda irregular_list: [element for item in irregular_list for element in
#                                                flatten_list(item)] if type(irregular_list) is list else [irregular_list]
#         instr_offsets = flatten_list(instr_offsets)
#
#         instr_offsets.sort()
#
#         remove_instr_offsets = [offset for item in instr_offsets for offset in range(item, item + 5)]
#
#         max_instr_offset = max(remove_instr_offsets)
#
#         left_instructions = []
#         offset = len(self.instructions_dict['prefix'])
#         for instruction in self.instructions_dict['middle']:
#             if not offset in remove_instr_offsets:
#                 left_instructions.append(instruction)
#             else:
#                 left_instructions.append({"address": instruction["address"], "opcode": "EMPTY"})
#             offset += 1
#
#         len_mid = len(left_instructions)
#         for i in range(len_mid):
#             if left_instructions[len_mid - i - 1]['opcode'].__eq__('EMPTY'):
#                 continue
#
#             if left_instructions[len_mid - i - 1]['opcode'].__eq__('DUP1'):
#                 left_instructions[len_mid - i - 1]['opcode'] = "EMPTY"
#             break
#
#         modify_instructions = self.instructions_dict['prefix'] + left_instructions + self.instructions_dict['suffix']
#
#         state.accounts[contract_address.value].code.instruction_list = copy(modify_instructions)
#         state.accounts[contract_address.value].code.func_hashes = fct_hashes
#
#     def _collect_pc_for_fct_hashes_in_dispatcher(self, laserEVM: LaserEVM):
#         """
#
#         """
#         if self._iteration_ == 1:
#             stop_flag = False
#             for state in laserEVM.open_states:
#                 if stop_flag: break  # collect only from a state at depth 1
#                 stop_flag = True
#                 key = contract_address.value
#                 code = state.accounts[key].code
#                 instructions = code.instruction_list
#                 self.instruction_list = code.instruction_list
#                 fct_instr_offsets = []
#
#                 function_hashes = code.func_hashes
#
#                 offset_instr = 0
#                 for instruction in instructions:
#                     opcode = instruction['opcode']
#                     if str(opcode).__eq__('PUSH4'):
#                         if instruction['argument'] in function_hashes:
#                             if not str(instruction['argument']) in self.fct_hash_2_pc_in_dispatcher.keys():
#                                 self.fct_hash_2_pc_in_dispatcher[str(instruction['argument'])] = offset_instr
#                             else:
#                                 self.fct_hash_2_pc_in_dispatcher[str(instruction['argument'])] = [offset_instr] + [
#                                     self.fct_hash_2_pc_in_dispatcher[str(instruction['argument'])]]
#                             fct_instr_offsets.append(offset_instr)
#                     offset_instr += 1
#                     if len(self.fct_hash_2_pc_in_dispatcher) == len(function_hashes):
#                         break
#                 # not yet consider the case of fallback functions
#                 min_offset = min(fct_instr_offsets)
#                 max_offst = max(fct_instr_offsets)
#                 self.instructions_dict['prefix'] = instructions[0:min_offset]
#                 self.instructions_dict['middle'] = instructions[min_offset:max_offst + 4]
#                 self.instructions_dict['suffix'] = instructions[max_offst + 4:]
#
#     def _get_function_selector(self, sig: str) -> str:
#         """'
#             Return the function id of the given signature
#         Args:
#             sig (str)
#         Return:
#             (int)
#         """
#         s = sha3.keccak_256()
#         s.update(sig.encode("utf-8"))
#         return '0x' + s.hexdigest()[:8]
