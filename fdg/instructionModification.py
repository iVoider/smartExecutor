from fdg.contractInfo import ContractInfo
from mythril.laser.ethereum.state.world_state import WorldState
from mythril.laser.ethereum.svm import LaserEVM


class InstructionModification():
    """
    change the function dispatcher at the beginning part of the instruction list
    """

    def __init__(self,contractInfo:ContractInfo):
        self.contractInfo=contractInfo
        self.instruction_list=[]
        self.instruction_dict={}
        self.instruction_extra_dict = {}
        self.ftn_to_position_in_dispatcher={} # save the order of functions in the dispatcher
        self.position_to_ftn_in_dispatcher={}
        self.contract_address=None

    def feed_instructions(self,laserEVM:LaserEVM,contract_address):
        self.contract_address=contract_address
        stop_flag = False
        for state in laserEVM.open_states:
            if stop_flag: break  # collect only from a state at depth 1
            stop_flag = True
            key = contract_address.value
            code = state.accounts[key].code
            instructions = code.instruction_list
            self.instruction_list=instructions

            offset_instr = 0
            ftn_count=0
            key="prefix"
            flag_status=0# change its value when "CALLDATASIZE" is met and the first PUSH after "CALLDATASIZE" is met

            address_jumpdest_revert_block=0
            self.instruction_dict[key]=[]
            for instruction in instructions:
                opcode = instruction['opcode']
                if str(opcode).__eq__('CALLDATASIZE'):
                    flag_status=1 # ready to get address of JUMPDEST for the block of revert
                elif str(opcode).__eq__('PUSH4'):
                    if flag_status==2:
                        if not str(instruction['argument']).__eq__('0xffffffff'):
                            key = instruction['argument']
                            if key in self.instruction_dict.keys(): # handle the case a function selector appears twice in the function dispatcher
                                self.instruction_extra_dict[key]= {}
                                self.instruction_extra_dict[key]["instructions"] = []
                                self.instruction_extra_dict[key]["position"] = ftn_count
                            else:
                                self.instruction_dict[key]=[]

                            if key in self.ftn_to_position_in_dispatcher.keys():
                                self.ftn_to_position_in_dispatcher[key] += [ftn_count]
                            else:
                                self.ftn_to_position_in_dispatcher[key]=[ftn_count]
                            self.position_to_ftn_in_dispatcher[ftn_count]=key
                            ftn_count+=1
                elif str(opcode).startswith('PUSH'):
                    if flag_status==1:
                        address_jumpdest_revert_block=int(instruction["argument"], 0)
                        flag_status=2 # ready to get matching instructions
                elif str(opcode).__eq__('JUMPDEST'):# the entry to the revert block when call data size is less than 4.before the code of functions
                    if flag_status==2:
                        if address_jumpdest_revert_block==instruction["address"]:
                            break

                offset_instr += 1

                if key in self.instruction_extra_dict.keys():
                    self.instruction_extra_dict[key]["instructions"] += [instruction]
                else:
                    self.instruction_dict[key] += [instruction]

            self.instruction_dict["suffix"] = instructions[offset_instr:]


    def modify_instructions_on_multiple_states(self, states: [WorldState], fct_selectors: list):
        """
            update the instructions on multiple states
        """

        final_instructions=self._get_modified_instructions(fct_selectors)
        for state in states:
            state.accounts[self.contract_address.value].code.instruction_list = final_instructions
            state.accounts[self.contract_address.value].code.func_hashes = fct_selectors

    def modify_instructions_on_one_state(self, state: WorldState, fct_selectors: list):
        """
            update the instructions on one state
        """
        final_instructions=self._get_modified_instructions(fct_selectors)
        state.accounts[self.contract_address.value].code.instruction_list = final_instructions
        state.accounts[self.contract_address.value].code.func_hashes = fct_selectors

    def _get_modified_instructions(self, fct_selectors: list)->list:
        """
            replace the matching instructions of other functions with EMPTY instruction
            keep the matching instructions of the specified functions
            * handle fallback() which has no selector
            * make sure that the last "DUP1" is replaced when the max position of the kept functions is not the last function
        """
        # the position of each function matching instruction is kept
        # the matching instructions of each function is kept

        # handle the case of the fallback()
        ftn_selectors_valid=fct_selectors
        if "None" in ftn_selectors_valid: ftn_selectors_valid.remove('None')

        # get the positions for functions to be executed
        ftn_positions=[]
        if len(ftn_selectors_valid)>0:
            for ftn in fct_selectors:
                if ftn not in self.ftn_to_position_in_dispatcher.keys():
                    print(f'{ftn} is unknown, either there is error in the extraction of matching instructions in the function dispatcher or it has only 3 bytes')
                else:
                    ftn_positions+=self.ftn_to_position_in_dispatcher[ftn]
            # ftn_positions=[self.ftn_to_position_in_dispatcher[ftn] for ftn in fct_selectors]

        if len(ftn_positions)>0:
            ftn_position_max=max(ftn_positions)
        else:
            ftn_position_max = len(self.position_to_ftn_in_dispatcher) - 1

        ftn_position_last= len(self.position_to_ftn_in_dispatcher) - 1

        flag_replace_DUP1=False
        if ftn_position_max<ftn_position_last:
            flag_replace_DUP1=True

        # reconstruct the instructions for the function dispatcher
        instruction_middle=[]
        for idx in range(len(self.position_to_ftn_in_dispatcher)): # keep the ascending order
            selector=self.position_to_ftn_in_dispatcher[idx] # find the function at position:idx
            # get the matching instructions for each function
            if selector in self.instruction_extra_dict.keys() and idx == self.instruction_extra_dict[selector][
                "position"]:
                instructions_selector=self.instruction_extra_dict[selector]["instructions"]
            else:
                instructions_selector = self.instruction_dict[selector]

            if selector in ftn_selectors_valid:
                if flag_replace_DUP1 and idx == ftn_position_max:
                    instruction_middle += instructions_selector[:-1]
                    instruction=instructions_selector[1]
                    instruction_middle.append({"address": instruction["address"], "opcode": "EMPTY"})
                else:
                    instruction_middle += instructions_selector
            else:
                # replace with EMPTY instructions
                for instruction in instructions_selector:
                    instruction_middle.append({"address": instruction["address"], "opcode": "EMPTY"})


        final_instructions=self.instruction_dict["prefix"]+ instruction_middle+self.instruction_dict["suffix"]

        return final_instructions


