import fdg
from fdg.FunctionCoverage import FunctionCoverage
from fdg.sequenceAndState import SequenceAndState


class SequenceExecutionControl():
    def __init__(self,sequenceAndState:SequenceAndState,functionCoverage:FunctionCoverage):
        self.sequenceAndState=sequenceAndState
        self.functionCoverage=functionCoverage
        self.deep_function=0 # integer
        self.flag_to_generate_sequences=True
        self.generated_sequences=[]
        self.sequence_cur_in_execution=[]
        self.sequence_index = 0
        self.function_index = 0

    def feed_generated_sequences(self,generated_sequences,deep_function_idx:int):
        """

        :param generated_sequences:
        :param deep_function_idx: the function that sequences are generated for
        :return:
        """
        assert len(generated_sequences)>0
        self.deep_function=deep_function_idx
        self.flag_to_generate_sequences = False
        self.generated_sequences = [seq for seq in generated_sequences if len(seq) <= fdg.FDG_global.seq_len_limit]
        self.sequence_index=0
        self.function_index=0
        self.sequence_cur_in_execution=self.generated_sequences[self.sequence_index]


    def end_exe_a_function(self):
        """
        update
        :return:
        """
        self.function_index+=1
        if self.function_index >= len(self.sequence_cur_in_execution): # finish executing a sequence
            # # check if the deep function is meaningfully executed, if yes, go to the next deep function
            # if self.sequenceAndState.has_state_changing_sequences(self.deep_function):
            #     self.flag_to_generate_sequences=True
            #     return

            # check if the deep function has 100% code coverage, if yes, go to the next deep function
            if not self.functionCoverage.is_a_deep_function(self.deep_function):
                self.flag_to_generate_sequences = True
                return
            self.sequence_index += 1
            if self.sequence_index >= len(self.generated_sequences):
                # all sequences are executed
                self.flag_to_generate_sequences=True
                return
            else:
                # update the sequence to be executed
                self.sequence_cur_in_execution = self.generated_sequences[self.sequence_index]
                self.function_index = 0


    def start_exe_a_function(self):
        """
        the prefix of the sequence has already executed. for example, the first two functions are executed (including the constructor)
        find initial stats, the start function for the sequence
        :param saved_open_states:
        :return:
        """
        if not self.flag_to_generate_sequences:
            if self.function_index==0: # the first time to execute a sequence
                # find the states to be executed
                key=str(self.sequence_cur_in_execution[0])
                for i in range(1,len(self.sequence_cur_in_execution)):
                    if self.sequenceAndState.has_state(key+str(self.sequence_cur_in_execution[i])):
                        key+=str(self.sequence_cur_in_execution[i])
                        self.function_index=i
                        continue
                    else:
                        break
                self.function_index+=1
                if self.function_index>=len(self.sequence_cur_in_execution):
                    # the sequence has already been executed(check)
                    return None,None
                else:
                    return key,self.sequence_cur_in_execution[self.function_index]
            else:
                return None,self.sequence_cur_in_execution[self.function_index]
        else:
            return None,None


    def need_to_generate_sequences(self)->bool:
        if len(self.sequence_cur_in_execution)==0:
            return True
        if self.sequence_index>=len(self.sequence_cur_in_execution):
            return True
        return  False


    def get_current_sequence_in_execution(self):
        return self.sequence_cur_in_execution[0:self.function_index+1]
