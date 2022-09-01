from fdg.FDG import FDG
from fdg.sequenceAndState import SequenceAndState


class DeepFunctionSelection():
    def __init__(self,fdg:FDG,sequenceAndState:SequenceAndState):
        self.FDG=fdg
        self.sequenceAndState=sequenceAndState
        self.selected_history=[]
        self.ftn_SV_has_parents={}

    def select_a_deep_function_simple(self, deep_functions:list):
        for ftn_idx in deep_functions:
            if ftn_idx in self.selected_history:continue # do not consider a function that has been considered
            self.selected_history.append(ftn_idx)
            return ftn_idx
        return -1

    def select_a_deep_function(self,deep_functions:list):
        """
        those functions are selected first, each parent group(writing the same state variables) of which has valid sequences
        :param deep_functions:
        :return:
        """
        target_ftn=-1
        for ftn_idx in deep_functions:
            if ftn_idx in self.selected_history: continue  # do not consider a function that has been considered

            if ftn_idx not in self.ftn_SV_has_parents.keys(): # for each deep function, save the status whether the parents of each SV it reads has state changing sequence or not
                # get the status of parents for each SV that the function(ftn_idx) reads
                self.ftn_SV_has_parents[ftn_idx]={}
                if self.FDG.has_parents(ftn_idx):
                    sv_parents = self.FDG.get_parents(ftn_idx)
                    target_flag=True
                    for sv, parents in sv_parents.items():
                        # check if there is a prent having state changing sequences
                        if self.sequenceAndState.has_state_changing_sequences_parents(parents):
                            self.ftn_SV_has_parents[ftn_idx][sv] = True
                        else:
                            self.ftn_SV_has_parents[ftn_idx][sv] = False
                            target_flag=False # once there is an SV, the corresponding parents have no state changing sequences, it is not the target function

                    if target_flag and target_ftn==-1: # found the first function that for each SV, there is parent sequence writting it

                        target_ftn=ftn_idx
                        break
            else:# update
                if len(self.ftn_SV_has_parents[ftn_idx])==0:continue # does not read any SVs
                target_flag = True
                for sv,has_prt_seq in self.ftn_SV_has_parents[ftn_idx].items():
                    if not has_prt_seq: # check if there is parent having state changing sequences
                        parents=self.FDG.get_parents_for_a_SV(ftn_idx,sv)
                        if self.sequenceAndState.has_state_changing_sequences_parents(parents):
                            self.ftn_SV_has_parents[ftn_idx][sv] = True
                        else:
                            self.ftn_SV_has_parents[ftn_idx][sv] = False
                            target_flag=False
                if target_flag and target_ftn==-1:
                    target_ftn=ftn_idx
                    break

        if target_ftn !=-1:
            self.selected_history.append(target_ftn)
            return target_ftn
        else:
            # randomly select in this case
            return self.select_a_deep_function_simple(deep_functions)




