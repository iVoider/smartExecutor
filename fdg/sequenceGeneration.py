
from fdg import utils
from fdg.FDG import FDG
import fdg.FDG_global
from fdg.merge_sequences import merge_sequences
from fdg.sequenceAndState import SequenceAndState


class SequenceGeneration():
    def __init__(self,fdg:FDG=None, sequenceAndState:SequenceAndState=None, phase1_depth=2):
        self.FDG=fdg
        self.sequenceAndState=sequenceAndState
        self.phase1_depth=phase1_depth

    def generate_sequences(self,ftn_idx)->list:
        # if fdg.FDG_global.phase2_method_select==0:
        sequences_paper = self.generate_sequences_paper(ftn_idx)

        sequences_paper.sort(key=len)

        if fdg.FDG_global.seq_num_limit==-1: # no limit on the number of sequences
            return sequences_paper
        else:
            if len(sequences_paper)>fdg.FDG_global.seq_num_limit:
                return sequences_paper[0:fdg.FDG_global.seq_num_limit]
            else:
                return sequences_paper

    def parent_sequences_write_one_SV(self, ftn_idx: int, parent_list: list, n: int, min_length: int) -> list:
        """
        get at most n parent sequences that write one SV and have length >= min_length
        :param parent_list: the parents to be considered
        :param n: specify the number of sequences returned
        :param min_length: the length of each sequence >= min_length
        :return:
        """

        parent_has_state_changing_sequences = [prt for prt in parent_list if
                                               self.sequenceAndState.has_state_changing_sequences_length(prt,
                                                                                                         min_length)]
        if n == -1:
            # get all state-changing sequences with length >= min_length
            sequences = self.sequenceAndState.get_all_state_changing_sequeces_length(
                parent_has_state_changing_sequences, self.phase1_depth)
        elif len(parent_has_state_changing_sequences) > n:
            # randomly select n
            sequences = self.sequenceAndState.get_shortest_state_changing_sequeces_length(
                parent_has_state_changing_sequences, self.phase1_depth)

        else:
            # get all state-changing sequences with length >= min_length
            sequences = self.sequenceAndState.get_all_state_changing_sequeces_length(
                parent_has_state_changing_sequences, self.phase1_depth)

        if len(sequences) > n and n > 0:
            sequences_selected = utils.random_select(sequences, n)
            return [seq + [ftn_idx] for seq in sequences_selected]
        else:#changed
            return [seq + [ftn_idx] for seq in sequences]

   

    def generate_sequences_paper(self,ftn_idx:int)->list:
        """
        get parent combinations
        one combination-> one sequence
        :param ftn_idx:
        :return:
        """
        sv_parents = self.FDG.get_parents(ftn_idx)
        if len(sv_parents) == 0: return []

        sv_list=list(sv_parents.keys())
        # sv_list =[2,3,4]
        generated_sequences=[] # to save the  generated sequences
        sv_combs=[]
        for length in range(1,len(sv_list)+1):
            sv_combs+=utils.get_combination_for_a_list(sv_list,length)
        for sv_comb in sv_combs:
            if len(sv_comb)==1:
                if isinstance(sv_parents, dict):
                    sequences = self.parent_sequences_write_one_SV(ftn_idx, sv_parents[sv_comb[0]],-1,
                                                                   self.phase1_depth)
                    for seq in sequences:
                        if seq not in generated_sequences:
                            generated_sequences.append(seq)
                else:
                    assert False, "data type error"
                continue

            # replace each sv with the corresponding parents
            sv_comb_parents=[sv_parents[sv] for sv in sv_comb]
            parent_combs=utils.get_combination(sv_comb_parents,len(sv_comb))
            for parent_comb in parent_combs:
                parent_comb=list(set(parent_comb))
                if len(parent_comb)<len(sv_comb):continue
                parent_sequence_list=[]
                flag_comb=True
                for parent in parent_comb:
                    parent_seq=self.sequenceAndState.get_n_shortest_state_changing_sequences_for_a_function(parent,1)
                    if len(parent_seq)==0:
                        flag_comb=False
                        break # if thre is one parent that does not have a parent sequence, ignore this parent combination
                    parent_sequence_list.append(parent_seq[0])
                if flag_comb:
                    generate_seq,_=merge_sequences(parent_sequence_list,ftn_idx,self.FDG.graph_dict)
                    if generate_seq not in generated_sequences:
                        generated_sequences.append(generate_seq)

        return generated_sequences


    def generate_sequences_for_functions_without_parents(self, ftn_idx: int):
        """
        on states that are generated at the depth 1
        :return:
        """
        sequences = []
        for length in range(1, fdg.FDG_global.phase1_depth_limit + 1):
            sequences += self.sequenceAndState.find_sequences_by_length(length)

        return [seq + [ftn_idx] for seq in sequences]



