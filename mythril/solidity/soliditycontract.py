"""This module contains representation classes for Solidity files, contracts
and source mappings."""
from typing import Dict, Set

import fdg
import mythril.laser.ethereum.util as helper
from mythril.ethereum.evmcontract import EVMContract
from mythril.ethereum.util import get_solc_json
from mythril.exceptions import NoContractFoundError


class SourceMapping:
    def __init__(self, solidity_file_idx, offset, length, lineno, mapping):
        """Representation of a source mapping for a Solidity file."""

        self.solidity_file_idx = solidity_file_idx
        self.offset = offset
        self.length = length
        self.lineno = lineno
        self.solc_mapping = mapping


class SolidityFile:
    """Representation of a file containing Solidity code."""

    def __init__(self, filename: str, data: str, full_contract_src_maps: Set[str]):
        """
        Metadata class containing data regarding a specific solidity file
        :param filename: The filename of the solidity file
        :param data: The code of the solidity file
        :param full_contract_src_maps: The set of contract source mappings of all the contracts in the file
        """
        self.filename = filename
        self.data = data
        self.full_contract_src_maps = full_contract_src_maps


class SourceCodeInfo:
    def __init__(self, filename, lineno, code, mapping):
        """Metadata class containing a code reference for a specific file."""

        self.filename = filename
        self.lineno = lineno
        self.code = code
        self.solc_mapping = mapping


def get_contracts_from_file(input_file, solc_settings_json=None, solc_binary="solc"):
    """

    :param input_file:
    :param solc_settings_json:
    :param solc_binary:
    """
    data = get_solc_json(
        input_file, solc_settings_json=solc_settings_json, solc_binary=solc_binary
    )

    try:
        contract_names = data["contracts"][input_file].keys()
    except KeyError:
        raise NoContractFoundError

    for contract_name in contract_names:
        if len(
            data["contracts"][input_file][contract_name]["evm"]["deployedBytecode"][
                "object"
            ]
        ):
            yield SolidityContract(
                input_file=input_file,
                name=contract_name,
                solc_settings_json=solc_settings_json,
                solc_binary=solc_binary,
            )


class SolidityContract(EVMContract):
    """Representation of a Solidity contract."""

    def __init__(
        self, input_file, name=None, solc_settings_json=None, solc_binary="solc"
    ):
        data = get_solc_json(
            input_file, solc_settings_json=solc_settings_json, solc_binary=solc_binary
        )

        self.solc_indices = self.get_solc_indices(data)
        self.solc_json = data
        self.input_file = input_file
        self.name=name #@wei

        has_contract = False

        # If a contract name has been specified, find the bytecode of that specific contract
        srcmap_constructor = []
        srcmap = []
        if name:
            contract = data["contracts"][input_file][name]
            if len(contract["evm"]["deployedBytecode"]["object"]):
                code = contract["evm"]["deployedBytecode"]["object"]
                creation_code = contract["evm"]["bytecode"]["object"]
                srcmap = contract["evm"]["deployedBytecode"]["sourceMap"].split(";")
                srcmap_constructor = contract["evm"]["bytecode"]["sourceMap"].split(";")
                fdg.FDG_global.method_identifiers = contract['evm']['methodIdentifiers']
                fdg.FDG_global.target_bytecode = code
                has_contract = True
        # If no contract name is specified, get the last bytecode entry for the input file
        else:
            for contract_name, contract in sorted(
                data["contracts"][input_file].items()
            ):
                if len(contract["evm"]["deployedBytecode"]["object"]):
                    name = contract_name
                    code = contract["evm"]["deployedBytecode"]["object"]
                    creation_code = contract["evm"]["bytecode"]["object"]
                    srcmap = contract["evm"]["deployedBytecode"]["sourceMap"].split(";")
                    srcmap_constructor = contract["evm"]["bytecode"]["sourceMap"].split(";" )
                    fdg.FDG_global.method_identifiers = contract['evm']['methodIdentifiers']
                    fdg.FDG_global.target_bytecode=code
                    has_contract = True

        if not has_contract:
            raise NoContractFoundError

        self.mappings = []

        self.constructor_mappings = []

        self._get_solc_mappings(srcmap)
        self._get_solc_mappings(srcmap_constructor, constructor=True)

        self.ftns_ast_srcmap={}
        self.ftns_instruction_indices={}
        self.get_function_instruction_indices()
        # @wei
        fdg.FDG_global.ftns_instr_indices = self.ftns_instruction_indices
        fdg.FDG_global.mapping = self.mappings
        fdg.FDG_global.solc_indices=self.solc_indices


        super().__init__(code, creation_code, name=name)


    #@wei
    def get_function_instruction_indices(self):
        # get the srcmap for each public/external function
        nodes_sourceUnit = self.solc_json['sources'][self.input_file]['ast']['nodes']
        for nodes_contractDefinition in nodes_sourceUnit:
            if nodes_contractDefinition['nodeType'] == 'ContractDefinition':
                con_name = nodes_contractDefinition['name']
                self.ftns_ast_srcmap[con_name] = {}
                for node in nodes_contractDefinition['nodes']:
                    if node['nodeType'] in ['FunctionDefinition','VariableDeclaration' ] and node['visibility'] in ['public', 'external']:
                        ftn_name = node['name']
                        if len(str(ftn_name))>0:
                            self.ftns_ast_srcmap[con_name][ftn_name] = [int(item) for item in str(node["src"]).split(':')]
                        else:
                            if 'kind' in node.keys():
                                ftn_name=node['kind']
                            elif 'isConstructor' in node.keys():
                                if node['isConstructor']:
                                    ftn_name='constructor'
                                else:ftn_name='fallback'
                            if ftn_name=='fallback':
                                self.ftns_ast_srcmap[con_name][ftn_name] = [int(item) for item in
                                                                            str(node["src"]).split(':')]

        # for each function, get indices of elements in mapping that the elements belong to it based on mapping.
        # the elements in mapping and their corresponding instructions have the same indices

        for idx in range(len(self.mappings)):
            file_idx = self.mappings[idx].solidity_file_idx
            if file_idx >= 0:
                offset = self.mappings[idx].offset
                length = self.mappings[idx].length
                save_flag = False
                for con_name_1, ftn_srcmap in self.ftns_ast_srcmap.items():
                    # look for function and its srcmap
                    for ftn_name, src in ftn_srcmap.items():
                        if offset >= src[0] and offset + length <= (src[0] + src[1]):
                            save_flag = True
                            break
                    if save_flag:
                        break
                if save_flag:
                    if ftn_name in self.ftns_instruction_indices.keys():
                        self.ftns_instruction_indices[ftn_name] += [idx]
                    else:
                        self.ftns_instruction_indices[ftn_name] = [idx]




    @staticmethod
    def get_solc_indices(data: Dict) -> Dict:
        """
        Returns solc file indices
        """
        indices = {}
        has_sources = True
        for contract_data in data["contracts"].values():
            for source_data in contract_data.values():
                if "generatedSources" not in source_data["evm"]["deployedBytecode"]:
                    has_sources = False
                    break
                sources = source_data["evm"]["deployedBytecode"]["generatedSources"]
                for source in sources:
                    full_contract_src_maps = SolidityContract.get_full_contract_src_maps(
                        source["ast"]
                    )
                    indices[source["id"]] = SolidityFile(
                        source["name"], source["contents"], full_contract_src_maps
                    )
            if has_sources is False:
                break
        for source in data["sources"].values():
            full_contract_src_maps = SolidityContract.get_full_contract_src_maps(
                source["ast"]
            )
            with open(source["ast"]["absolutePath"]) as f:
                code = f.read()
                indices[source["id"]] = SolidityFile(
                    source["ast"]["absolutePath"], code, full_contract_src_maps
                )
        return indices

    @staticmethod
    def get_full_contract_src_maps(ast: Dict) -> Set[str]:
        """
        Takes a solc AST and gets the src mappings for all the contracts defined in the top level of the ast
        :param ast: AST of the contract
        :return: The source maps
        """
        source_maps = set()
        if ast["nodeType"] == "SourceUnit":
            for child in ast["nodes"]:
                if child.get("contractKind"):
                    source_maps.add(child["src"])
        elif ast["nodeType"] == "YulBlock":
            for child in ast["statements"]:
                source_maps.add(child["src"])

        return source_maps

    def get_source_info(self, address, constructor=False):
        """

        :param address:
        :param constructor:
        :return:
        """
        disassembly = self.creation_disassembly if constructor else self.disassembly
        mappings = self.constructor_mappings if constructor else self.mappings
        index = helper.get_instruction_index(disassembly.instruction_list, address)

        solidity_file = self.solc_indices[mappings[index].solidity_file_idx]
        filename = solidity_file.filename

        offset = mappings[index].offset
        length = mappings[index].length

        code = solidity_file.data.encode("utf-8")[offset : offset + length].decode(
            "utf-8", errors="ignore"
        )
        lineno = mappings[index].lineno
        return SourceCodeInfo(filename, lineno, code, mappings[index].solc_mapping)

    def _is_autogenerated_code(self, offset: int, length: int, file_index: int) -> bool:
        """
        Checks whether the code is autogenerated or not
        :param offset: offset of the code
        :param length: length of the code
        :param file_index: file the code corresponds to
        :return: True if the code is internally generated, else false
        """

        if file_index == -1:
            return True
        # Handle the common code src map for the entire code.
        if (
            "{}:{}:{}".format(offset, length, file_index)
            in self.solc_indices[file_index].full_contract_src_maps
        ):
            return True

        return False

    def _get_solc_mappings(self, srcmap, constructor=False):
        """

        :param srcmap:
        :param constructor:
        """
        mappings = self.constructor_mappings if constructor else self.mappings
        prev_item = ""
        for item in srcmap:
            if item == "":
                item = prev_item
            mapping = item.split(":")

            if len(mapping) > 0 and len(mapping[0]) > 0:
                offset = int(mapping[0])

            if len(mapping) > 1 and len(mapping[1]) > 0:
                length = int(mapping[1])

            if len(mapping) > 2 and len(mapping[2]) > 0:
                idx = int(mapping[2])

            if self._is_autogenerated_code(offset, length, idx):
                lineno = None
            else:
                lineno = (
                    self.solc_indices[idx]
                    .data.encode("utf-8")[0:offset]
                    .count("\n".encode("utf-8"))
                    + 1
                )
            prev_item = item
            mappings.append(SourceMapping(idx, offset, length, lineno, item))

