


from fdg.contractInfo import ContractInfo



SV_NOT_CONSIDER=['mapping','array']
class FDG():

    def __init__(self,contractInfo:ContractInfo,level_phase1=0,level_phase2=1):
        """
        :param contractInfo:
        :param level:
            0: all state variables read
            1: state variables read in conditions
            others: primitive state variables in conditions
        """
        self.contractInfo=contractInfo
        self.graph_dict={}
        self.level_phase1=level_phase1
        self.level_phase2=level_phase2
        self._generate_graph()

        self.function_parents={}
    def get_ftn_read_SV(self,sv:str,level:int)->list:
        """
        get all parents that read sv
        :param sv:
        :return:
        """
        re=[]
        type="read_sv" if level==0 else "read_sv_condition"
        for ftn_idx in range(2, len(self.contractInfo.get_function_indices())):
            if sv in self.contractInfo.get_function_info(ftn_idx,type):
                re.append(ftn_idx)
        return re

    def get_children(self, ftn_idx:int)->list:
        if ftn_idx in self.graph_dict.keys():
            return self.graph_dict[ftn_idx]
        else:
            return []

    def has_parents(self,ftn_idx:int)->bool:
        def _has_values( sv_parents_dict:dict)->bool:
            if len(sv_parents_dict)==0:
                return False # no state variable that it reads
            for values in sv_parents_dict.values():
                if len(values)>0:
                    return True  # there are parents on at least one state variable
            return False # no parents on each state variable

        if ftn_idx in self.function_parents.keys():
            return _has_values(self.function_parents[ftn_idx])
        else:
            self._find_parents(ftn_idx,self.level_phase2)# find
            return _has_values(self.function_parents[ftn_idx])

    def get_parents_for_a_SV(self,ftn_idx:int, SV:str)->list:
        """
        get the parents that write SV (ftn_idx reads SV)
        :param ftn_idx:
        :param SV:
        :return:
        """
        assert(ftn_idx in self.function_parents.keys())
        assert (SV in self.function_parents[ftn_idx].keys())
        return self.function_parents[ftn_idx][SV]

    def get_parents(self,ftn_idx:int)->dict:
        if ftn_idx in self.function_parents.keys():
            return self.function_parents[ftn_idx]
        else: return self._find_parents(ftn_idx,self.level_phase2)

    def get_parent_list(self,ftn_idx:int)->list:
        """
        get all parents for a function
        :param ftn_idx:
        :return:
        """
        sv_parents=self.get_parents(ftn_idx)
        if len(sv_parents)>0:
            prt_list=[]
            for parents in sv_parents.values():
                prt_list+=parents
            return list(set(prt_list))
        else: return []

    def _generate_graph(self):
        for ftn_idx in self.contractInfo.get_function_indices():
            children_nodes=self._find_children(ftn_idx, self.level_phase1)
            if ftn_idx not in self.graph_dict.keys():
                self.graph_dict[ftn_idx] = children_nodes

    def _find_children(self, ftn_idx: int, level:int) -> list:
        children_indices = []
        sv_written = self.contractInfo.get_function_info(ftn_idx,"write_sv")
        if len(sv_written) == 0: return []
        for sv_w in sv_written:
            for idx in self.contractInfo.get_function_indices() - [0]:  # do not consider constructor
                sv_read = self._get_sv_read(idx,level)
                if sv_w in sv_read:
                    if idx not in children_indices:
                        children_indices.append(idx)
        return children_indices


    def _find_parents(self, ftn_idx: int, level: int) -> list:
        """
        :param ftn_idx:
        :param level:
        :return: {sv: parent_list,...}
        """
        parents= {}
        if ftn_idx not in self.contractInfo.get_function_indices():
            print(f'function {ftn_idx} does not have static info.')
            self.function_parents[ftn_idx] = parents
            return parents

        sv_read=self._get_sv_read(ftn_idx, level)
        if len(sv_read) == 0:
            self.function_parents[ftn_idx] = parents
            return parents

        for sv_r in sv_read:
            parents[sv_r]=[]
            for idx in self.contractInfo.get_function_indices()-[0]:
                sv_written = self.contractInfo.get_function_info(idx,"write_sv")
                if sv_r in sv_written:
                    if idx==ftn_idx: continue # do not consider itself
                    parents[sv_r].append(idx)
        self.function_parents[ftn_idx]=parents
        return parents


    def _get_sv_read(self, ftn_idx: int, level) -> list:
        if level == 1:
            sv_read = self.contractInfo.get_function_info(ftn_idx,"read_sv_condition")
        elif level == 0:
            sv_read = self.contractInfo.get_function_info(ftn_idx,"read_sv")
        else:
            sv_read = self.contractInfo.get_function_info(ftn_idx,"read_sv_condition")
            if len(self.contractInfo.stateVariable_info.keys()) > 0:
                sv_read = [sv for sv in sv_read if self.contractInfo.get_state_variable_type(sv) not in ['mapping','array']]
        return sv_read







if __name__=='__main__':
    pass












