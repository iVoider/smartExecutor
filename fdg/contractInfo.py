from slither.core.declarations.function_contract import FunctionContract
from slither.slither import Slither

import fdg

import sha3

class ContractInfo():
    def __init__(self,solidity_file:str, contract_name:str,method_identifiers:dict):
        self.solidity_file=solidity_file
        self.contract_name=contract_name.lstrip().rstrip()
        self.method_identifiers=method_identifiers
        self.slither_contract=Slither(self.solidity_file).get_contract_from_name(self.contract_name)

        self.function_info = {}
        self.stateVariable_info = {}
        self.ftn_to_idx={}
        self.ftn_to_selector={}
        self.ftnPureName_to_ftnFullName={}

        self._get_state_variable_info()
        self._get_user_callable_function_info_1()

        self.fdg_parents={}

    def _get_state_variable_info(self):
        for sv in self.slither_contract.state_variables:
            sv_type=str(sv.type)
            if str(sv_type).startswith('mapping'):
                sv_type='mapping'
                self.stateVariable_info[sv.name] = [sv.type,fdg.FDG_global.non_primitive_index]
            elif str(sv_type).startswith('array'):
                sv_type = 'array'
                self.stateVariable_info[sv.name] = [sv.type,fdg.FDG_global.non_primitive_index]
            else:
                self.stateVariable_info[sv.name] = [sv.type,fdg.FDG_global.primitive_index]
            # print(f'{sv}:{sv.type}')

    def get_sv_type(self, sv:str)->int:
        assert sv in self.stateVariable_info.keys()
        return self.stateVariable_info[sv][1]

    def _get_user_callable_function_info(self):
        ftn_idx=2 # 0: constructor; 1: fallback
        functions_considered=[]
        temp=0
        for f in self.slither_contract.functions:
            if f.name.__eq__('slitherConstructorVariables'): continue
            if f.name.__eq__('slitherConstructorConstantVariables'): continue

            if f.name.__eq__(self.contract_name): continue
            if f.is_constructor: continue

            # only consider public, external functions
            summary = f.get_summary()
            if len(summary) >= 3:
                if summary[2] not in ['public', 'external']:
                    continue

            if f.full_name not in functions_considered:
                functions_considered.append(f.full_name)
                f_info=self._get_a_function_info(f)
                if f.name.__eq__("fallback"):
                    temp=ftn_idx
                    ftn_idx=1
                self.function_info[ftn_idx]=f_info
                self.ftn_to_idx[f.full_name] =ftn_idx
                self.ftn_to_selector[f.full_name]=f_info["selector"]
                self.ftnPureName_to_ftnFullName[f.name]=f.full_name

                if f.name.__eq__("fallback"):
                    ftn_idx=temp
                else:
                    ftn_idx += 1

        if 1 not in self.function_info.keys(): #
            self.function_info[1] = {"name": "fallback()", "write_sv": [], "read_sv": [], "read_sv_condition": [],
                    "selector": "None"}
            self.ftn_to_idx['fallback()']=1
            self.ftnPureName_to_ftnFullName["fallback"]="fallback()"

        self.function_info[0]= {"name": "constructor()", "write_sv": [], "read_sv": [], "read_sv_condition": [],
                    "selector": "None"}
        self.ftn_to_idx['constructor()'] = 0

    def _get_user_callable_function_info_1(self):
        ftn_idx = 2  # 0: constructor; 1: fallback
        functions_considered = []
        temp = 0
        for f in self.slither_contract.all_functions_called:
            if f.name.__eq__('slitherConstructorVariables'): continue
            if f.name.__eq__('slitherConstructorConstantVariables'): continue

            if f.name.__eq__(self.contract_name): continue
            if f.is_constructor: continue
            if f.view:continue
            # only consider public, external functions
            summary = f.get_summary()
            if len(summary) >= 3:
                if summary[2] not in ['public', 'external']:
                    continue
            # do not use the full_name obtained from Slither as it does not match the full name ocassionally in Mythril)
            if f.full_name not in functions_considered:

                functions_considered.append(f.full_name)
                f_info = self._get_a_function_info(f)
                if f.name.__eq__("fallback"):
                    temp = ftn_idx
                    ftn_idx = 1
                self.function_info[ftn_idx] = f_info
                self.ftn_to_idx[f_info['name']] = ftn_idx
                self.ftn_to_selector[f_info['name']] = f_info["selector"]
                self.ftnPureName_to_ftnFullName[f.name] = f_info['name']

                if f.name.__eq__("fallback"):
                    ftn_idx = temp
                else:
                    ftn_idx += 1

        if 1 not in self.function_info.keys():  #
            self.function_info[1] = {"name": "fallback()", "write_sv": [], "read_sv": [], "read_sv_condition": [],
                                     "selector": "None"}
            self.ftn_to_idx['fallback()'] = 1
            self.ftnPureName_to_ftnFullName["fallback"] = "fallback()"

        self.function_info[0] = {"name": "constructor()", "write_sv": [], "read_sv": [], "read_sv_condition": [],
                                 "selector": "None"}
        self.ftn_to_idx['constructor()'] = 0

    def get_index_from_name(self, ftn_name:str):
        assert ftn_name in self.ftn_to_idx.keys()
        return self.ftn_to_idx[ftn_name]

    def get_name_from_index(self,ftn_idx:int):
        assert ftn_idx in self.function_info.keys()
        return self.function_info[ftn_idx]['name']

    def get_selector_from_index(self,ftn_idx):

        if ftn_idx in self.function_info.keys():
            return self.function_info[ftn_idx]['selector']
        else:return 'None'

    def get_state_variable_type(self,sv:str):
        assert sv in self.stateVariable_info.keys()
        return self.stateVariable_info[sv][0]

    def get_function_info(self,ftn_idx:int,info_type:str):
        assert ftn_idx in self.function_info.keys()
        return self.function_info[ftn_idx][info_type]

    def get_function_indices(self):
        return self.function_info.keys()


    def _get_a_function_info(self, ftn:FunctionContract):
        """

        :param ftn:
        :return: a dict having info including name, write list, read list, read list of state variable read in conditions, hash
        """
        w_list = []
        f_w = ftn.all_state_variables_written()
        if len(f_w) > 0:
            w_list = [sv.name for sv in f_w]

        r_list = []
        f_r = ftn.all_state_variables_read()
        if len(f_r) > 0:
            # consider state variables read in all conditions
            r_list = [sv.name for sv in f_r]

        r_list_condition = []
        f_r_condition = ftn.all_conditional_state_variables_read()
        if len(f_r_condition) > 0:
            # consider state variables read in all conditions
            r_list_condition = [sv.name for sv in f_r_condition]

        if ftn.name.__eq__('fallback'):
            func_hash = 'None'
            return {"name":ftn.full_name,"write_sv":w_list,"read_sv":r_list,"read_sv_condition":r_list_condition,"selector":func_hash}
        else:
            func_hash = None
            # # get function hash based on information in Slither
            # func_hash = self._get_function_selector(ftn.full_name)

            # get function hash from given information
            ftn_full_name = ftn.full_name
            if ftn_full_name in self.method_identifiers.keys():
                func_hash = "0x" + self.method_identifiers[ftn.full_name]
            else:
                for full_name, hash in self.method_identifiers.items():
                    pure_name = str(full_name).split("(")[0]
                    if ftn.name.__eq__(pure_name):
                        func_hash = "0x" + hash
                        ftn_full_name = full_name

            return {"name": ftn_full_name, "write_sv": w_list, "read_sv": r_list, "read_sv_condition": r_list_condition,
                    "selector": func_hash}

    def _get_function_selector(self, sig: str) ->str:
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


if __name__=='__main__':
    # ftn_info = Function_info('/home/wei/PycharmProjects/Contracts/_wei/wei_test.sol', 'wei_test')
    # ftn_info = Function_info('/home/wei/PycharmProjects/Contracts/_wei/wei_test.sol', 'wei_test')
    # ftn_info = Function_info('/home/wei/PycharmProjects/Contracts/_wei/play_me_quiz.sol', 'play_me_quiz')
    # ftn_info = Function_info('/home/wei/PycharmProjects/Contracts/example_contracts/ZetTokenMint.sol', 'ZetTokenMint')
    # ftn_info = Function_info('/home/wei/PycharmProjects/Contracts/example_contracts/AaronTestCoin.sol', 'AaronTestCoin')
    # ftn_info = ContractData('/home/wei/PycharmProjects/Contracts/example_contracts/DxLockEth4Rep.sol', 'Avatar')
    #conData = ContractData('/home/wei/PycharmProjects/Contracts/_wei/Crowdsale.sol', 'Crowdsale')
    #conData = ContractData('/home/wei/PycharmProjects/Contracts/_wei/HoloToken.sol', 'HoloToken')
    #conData = ContractData('/media/sf___share_vms/temp/PDC_2.sol', 'PDC_2')

    #conData = ContractData('/media/sf___share_vms/temp/SMT.sol', 'SMT')
    # conData = ContractData('/media/sf___share_vms/temp/Overflow.sol', 'Overflow')
    conData = ContractInfo('/media/sf___share_vms/temp/PDC_7.sol', 'PDC_7')

    # conData=ContractData('/media/sf___share_vms/temp/PDC.sol', 'PDC')
    conData.get_state_variables_info()
    conData.get_user_callable_functions_info()

    for key, value in conData.functions_info.items():
        print(f'{key}')
        for k,v in value.items():
            print(f'{k}:{v}')
    # ftn_dict= ftn_info.functions_dict_slither()
    # print("===== ftn_dict ====")
    # for key, value in ftn_dict.items():
    #     print("\t{}:  {}".format(key, value))
    # pass



    # a=[24, 29, 189, 34, 118, 194, 265, 39]
    # pairs=get_valid_pc_interval(a,1000)
    # if pc_is_valid(90,pairs):
    #     print(f'90 is in {pairs}')
