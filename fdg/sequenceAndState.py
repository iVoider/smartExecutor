from copy import copy

from fdg.contractInfo import ContractInfo
from fdg.FunctionCoverage import FunctionCoverage
from mythril.laser.ethereum.state.world_state import WorldState
from mythril.laser.plugin.plugins.dependency_pruner import get_ftn_seq_annotation_from_ws

from fdg import utils

class SequenceAndState():
    def __init__(self,contractInfo:ContractInfo,functionCoverage:FunctionCoverage):
        self.contractInfo=contractInfo
        self.functionCoverage=functionCoverage
        self.worldState_dict={}
        self.sequence_changing_state_dict={}
        self.sequence_not_changing_state_dict={}

        self.function_parents={}




    def save_state_and_its_sequence(self,state:WorldState)->list:
        """
        assume that the constraints of the state is satisfied (i.e., they are checked before being passed to this function
        :param state:
        :return:
        """

        ftn_seq = get_ftn_seq_annotation_from_ws(state)

        ftn_idx_seq=[]
        for ftn_name in ftn_seq:
            if ftn_name not in self.contractInfo.ftn_to_idx.keys():
                ftn_idx_seq.append(ftn_name) # to-do-list # ftn_name is a function of a public state variable (not in the FDG)

            else:
                ftn_idx_seq.append(self.contractInfo.get_index_from_name(ftn_name))
        # save the state
        key=self.generate_key(ftn_idx_seq)
        if key in self.worldState_dict.keys():
            self.worldState_dict[key]+=[copy(state)] # check if deepcopy is needed
        else:
            self.worldState_dict[key]=[copy(state)]

        # save the sequence: the last element is the key
        if ftn_idx_seq[-1] in self.sequence_changing_state_dict.keys():
            if ftn_idx_seq not in self.sequence_changing_state_dict[ftn_idx_seq[-1]]:
                self.sequence_changing_state_dict[ftn_idx_seq[-1]]+=[ftn_idx_seq]
        else:
            self.sequence_changing_state_dict[ftn_idx_seq[-1]] = [ftn_idx_seq]
        return ftn_idx_seq

    def save_sequences_not_changing_states(self,all_sequences:list,state_changing_sequences:list):
        for seq in all_sequences:
            if seq not in state_changing_sequences:
                if seq[-1] in self.sequence_not_changing_state_dict.keys():
                    if seq not in self.sequence_not_changing_state_dict[seq[-1]]:
                        self.sequence_not_changing_state_dict[seq[-1]]+=[seq]
                else:
                    self.sequence_not_changing_state_dict[seq[-1]] = [seq]

    def generate_key(self,sequence:list)->str:
        if len(sequence)==1:
            return str(sequence[0])
        else:
            key=str(sequence[0])
            for idx in sequence[1:]:
                key+=str(idx)
            return key

    def has_state(self,key)->bool:
        if key in self.worldState_dict.keys():
            return True
        else:return False
    def get_state(self,key)->[WorldState]:
        if key in self.worldState_dict.keys():
            return self.worldState_dict[key]
        else:return []



    def has_state_changing_sequences(self,ftn_idx:int)->bool:
        if ftn_idx in self.sequence_changing_state_dict.keys():
            return True
        else: return False

    def has_state_changing_sequences_length(self,ftn_idx:int,min_length:int)->bool:
        """
        require the length of state changing sequences >= min_length
        :param ftn_idx:
        :param min_length:
        :return:
        """
        if ftn_idx in self.sequence_changing_state_dict.keys():
            for seq in self.sequence_changing_state_dict[ftn_idx]:
                if len(seq)>=min_length:
                    return True
        else: return False

    def has_state_changing_sequences_parents(self, parents:list)->bool:
        for prt_idx in parents:
            if self.has_state_changing_sequences(prt_idx):
                return True
        return False

    def get_all_state_changing_sequeces_length(self,prt_list:list,min_length:int)->list:
        """
        for each parent, get all the state-changing sequences with length >= min_length

        :param prt_list:
        :param min_length:
        :return:
        """
        sequences=[]
        for prt in prt_list:
            if prt not in self.sequence_changing_state_dict.keys():continue
            for seq in self.sequence_changing_state_dict[prt]:
                if len(seq)>=min_length:
                    if seq not in sequences:
                        sequences.append(seq)
        return sequences

    def get_shortest_state_changing_sequeces_length(self,prt_list:list,min_length:int)->list:
        """
        for each parent, get a shortest sequence with length >=min_length

        :param prt_list:
        :param min_length:
        :return:
        """
        sequences=[]
        for prt in prt_list:
            if prt in self.sequence_changing_state_dict.keys():
                seq_list=list(self.sequence_changing_state_dict[prt])
                seq_list.sort(key=len)
                for seq in seq_list:
                    if len(seq)>=min_length:
                        if seq not in sequences:
                            sequences.append(seq)
                            break
        return sequences

    def get_state_changing_sequences(self,ftn_idx:int)->list:
        if ftn_idx not in self.sequence_changing_state_dict.keys():
            return []
        return self.sequence_changing_state_dict[ftn_idx]

    def get_n_state_changing_sequences_for_a_parent(self, ftn_idx:int, specified_num:int)->list:
        if ftn_idx not in self.sequence_changing_state_dict.keys():
            return []
        sequnces=self.sequence_changing_state_dict[ftn_idx]
        sequnces.sort(key=len)
        if len(sequnces)>specified_num:
            return sequnces[0:specified_num]
        else:
            return sequnces


    def get_n_state_changing_sequences_from_multiple_parents(self, parents:list, n:int):
        """
        from a list of parents, return a specified number of parent sequences
        :param parents:
        :param n:
        :return:
        """
        parent_has_SCS = [prt for prt in parents if self.has_state_changing_sequences(prt)]
        if len(parent_has_SCS)>=n:
            sequences=[]
            for prt in parent_has_SCS:
                seq_list=self.get_n_shortest_state_changing_sequences_for_a_function(prt,1)
                if len(seq_list)>0:
                    for seq in seq_list:
                        if seq not in sequences:
                            sequences.append(seq)
            return utils.random_select(sequences, n)
        else:
            sequences=[]
            for prt in parent_has_SCS:
                seq_list=self.get_n_shortest_state_changing_sequences_for_a_function(prt,2)
                if len(seq_list)>0:
                    for seq in seq_list:
                        if seq not in sequences:
                            sequences.append(seq)
            return utils.random_select(sequences, n)



    def get_n_shortest_state_changing_sequences_for_a_function(self, ftn_idx,n:int)->list:
        if ftn_idx not in self.sequence_changing_state_dict.keys():
            return []
        sequences=self.sequence_changing_state_dict[ftn_idx]
        if len(sequences)>n:
            sequences.sort(key=len)
            return sequences[0:n]
        else: return sequences

    def get_n_shortest_state_changing_sequences_for_a_function_length(self, ftn_idx,n:int,min_length:int)->list:
        if ftn_idx not in self.sequence_changing_state_dict.keys():
            return []
        sequences=self.sequence_changing_state_dict[ftn_idx]
        if len(sequences)==0: return sequences
        seq_fix_len=[]
        sequences.sort(key=len)
        for seq in sequences:
            if len(seq)>=min_length:
                seq_fix_len.append(seq)
        if len(seq_fix_len)>n:
            return seq_fix_len[0:n]
        else: return seq_fix_len

    def get_not_state_changing_sequences(self,ftn_idx:int)->list:
        if ftn_idx not in self.sequence_not_changing_state_dict.keys():
            return []
        else: return self.sequence_not_changing_state_dict[ftn_idx]

    def is_within_not_state_changing_sequences(self,seq:list)->bool:
        if seq[-1] in self.sequence_not_changing_state_dict.keys():
            if seq in self.sequence_not_changing_state_dict[seq[-1]]:
                return True
        return False

    def find_sequences_by_length(self,length:int)->list:
        sequences=[]
        for values in self.sequence_changing_state_dict.values():
            for seq in values:
                if len(seq)==length:
                    sequences.append(seq)
        return sequences





