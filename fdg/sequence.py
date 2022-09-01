from copy import copy
from itertools import permutations, combinations
import numpy as np
import itertools as it

import fdg
from fdg import lists_merge, utils

import fdg.FDG_global

"""
all parent will be represented by its shortest sequences
sequence generation level:

1: all parents, merge sequences
2: all parents, topological sorting in sequence generation
3: parent subsets, merge sequences
4: parent subsets, topological sorting in sequence generation
5: randomly select parents, topological sorting in sequence generation
6: randomly select parents + a special case (all parents are considered), topological sorting in sequence generation

"""


class Sequence():
    def __init__(self, fdg_=None, ftn_idx_not_covered=[], valid_sequences={}, prt_subset_num_limit=5, seq_num_limit=1):
        self.fdg = fdg_
        self.uncovered_ftn_idx = ftn_idx_not_covered  # target function
        self.seq_num_limit = seq_num_limit
        self.prt_subset_num_limit = prt_subset_num_limit

        self.valid_sequences_given = valid_sequences
        self.valid_sequences_given_transformed = {}  # replace self.all_valid_sequences
        self.valid_seq_dict = {}
        self.assignment_sequence = []
        self.sequences_generated = []
        self.sequences_generated_cur = {}

        self.uncovered_ftn_idx = ftn_idx_not_covered
        self.uncovered_ftn_idx_waiting = []

        self.ftn_idx_to_column_idx = {}
        self.column_idx_to_ftn_idx = {}
        self.package_list = []

        self.ftn_no_sequences = []

        self.flag_all_ftn_considered = False
        # ==================================
        # prepare data for topological sorting checking
        # remove cycles in edge list
        edges_without_cycles = []
        edges_cycles = []
        for edge in self.fdg.edges_no_f:
            if edge[0] == edge[1]:
                continue
            if [edge[1], edge[0]] in self.fdg.edges_no_f:
                edges_cycles.append(edge)
                continue
            edges_without_cycles.append(edge)
        self.parents = {}
        for edge in edges_without_cycles:
            if edge[1] in self.parents.keys():
                if edge[0] not in self.parents[edge[1]]:
                    self.parents[edge[1]].append(edge[0])
            else:
                self.parents[edge[1]] = [edge[0]]

    def _get_label_parent(self, ftn_idx) -> dict:
        """
        get parents and their labels based on the write and read of state variables
        :param ftn_idx:
        :return:dict: key: label index, value: parent indices
        """
        l_p_dict = {}
        sv_read_ary = self.fdg.sv_read[ftn_idx, :]
        sv_read = sv_read_ary[sv_read_ary >= 0]
        for sv in sv_read:
            ftn_write_ary = self.fdg.sv_write[:, sv]
            ftn_write = np.where(ftn_write_ary >= 0)[0]
            l_p_dict[sv] = [ftn_i for ftn_i in ftn_write if ftn_i != ftn_idx]
        return l_p_dict

    def _get_parent(self, ftn_idx) -> dict:
        """
        get parents
        :param ftn_idx:
        :return:[parent idx]
        """

        parents = []
        sv_read_ary = self.fdg.sv_read[ftn_idx, :]
        sv_read = sv_read_ary[sv_read_ary >= 0]
        for sv in sv_read:
            ftn_write_ary = self.fdg.sv_write[:, sv]
            ftn_write = np.where(ftn_write_ary >= 0)[0]
            parents += [ftn_i for ftn_i in ftn_write if ftn_i != ftn_idx]

        return list(set(parents))

    def _valid_sequence_transform(self, sequence_of_sequences: list):
        if len(sequence_of_sequences) > 0:
            ele_size = [len(item) for item in sequence_of_sequences]
            min_size = min(ele_size)
            shortest_seq = [item for item in sequence_of_sequences if len(item) == min_size]
            return {'sequences': sequence_of_sequences, 'seq_num': len(sequence_of_sequences),
                    'shortest': shortest_seq,
                    'shortest_depth': min_size}
        else:
            return {'sequences': [], 'seq_num': 0, 'shortest': [],
                    'shortest_depth': 0}

    def _merge_parent_sequence_list(self, parent_sequence_list: list, ftn_idx):
        """
        each permulation of nested list is created one sequence
        the prefix of the first sequence is fixed
        :param nested_list:
        :return:
        """
        result = []
        ele_num = len(parent_sequence_list)
        if ele_num == 1: return []

        permulation_nested_list = permutations(parent_sequence_list)
        for per_tuple in permulation_nested_list:
            temp_list = list(per_tuple)
            p_first = temp_list[0]
            p_first_length = len(temp_list[0])
            merge_seq = p_first
            for i in range(1, ele_num):
                merge_seq = lists_merge.merge_fix_list_1_specified_lenth_no_repeated_elements(merge_seq, temp_list[i],
                                                                                              p_first_length)
            # form final sequence
            if merge_seq not in result:
                result.append(merge_seq)
            if len(result) >= self.seq_num_limit: break

        final_sequences = []
        for seq in result:
            seq_ = seq + [ftn_idx]
            final_sequences.append(seq_)
        return final_sequences

    def _merge_sequences_ordered(self, nested_list: list):
        """
        get one sequence from one parent subset
        the prefix of the first sequence is fixed
        :param nested_list:
        :return:
        """

        ele_num = len(nested_list)
        if ele_num == 1: return []
        # order elements in nested_list based on len
        order_nested_list = sorted(nested_list, key=len, reverse=True)

        # merge sequence
        p_first = order_nested_list[0]
        p_first_length = len(order_nested_list[0])
        merge_seq = p_first

        for i in range(1, ele_num):
            merge_seq = lists_merge.merge_fix_list_1_specified_lenth_no_repeated_elements(merge_seq,
                                                                                          order_nested_list[i],
                                                                                          p_first_length)

        # form final sequence
        # remove the elements from the first parent
        final_seq = [[p_first_length, p_first[-1]]]
        final_seq += merge_seq[p_first_length:]
        return [final_seq]

        # consider only the shortest sequences for each parent

    def _merge_sequences(self, nested_list: list):
        '''
        no permutation, no ordering
        the prefix of the first sequence is not fixed
        :param nested_list:
        :return:
        '''
        ele_num = len(nested_list)
        if ele_num == 1: return []

        # merge sequence
        merge_seq = nested_list[0]

        for i in range(1, ele_num):
            merge_seq = lists_merge.merge_two_list(merge_seq, nested_list[i])

        # form final sequence
        # remove the elements from the first parent
        final_seq = [[1, nested_list[0][0]]]
        final_seq += merge_seq[1:]
        return [final_seq]



    #  consider all parent subsets,topological sorting,
    def _get_sequences_by_level_2(self, parent_groups: list, ftn_idx):
        """
        consider all parent subsets
        use shortest sequences to represent parents
        topological sorting in sequence merging process
        :return:
        """
        final_sequences = []
        if len(parent_groups) == 0: return []

        # consider each parent individually
        parents = [p for p_list in parent_groups for p in p_list]
        parents = list(set(parents))
        for p_idx in parents:
            seq_gen = self._get_sequence_1_parent_considered(p_idx, ftn_idx)
            for seq in seq_gen:
                if seq not in final_sequences:
                    final_sequences.append(seq)

        # conside two or more parents
        if len(parent_groups) > 1:
            parent_subsets = []
            for i in range(1, len(parent_groups)):
                parent_combinations = utils.get_combination(parent_groups, i + 1)
                for com in parent_combinations:
                    parent_subsets.append(list(com))

            for p_subset in parent_subsets:
                parent_sequences = self._get_parent_sequnces(p_subset)
                for p_seq in parent_sequences:
                    sequences = self._get_topological_sequences(p_seq, ftn_idx)
                    for seq in sequences:
                        if seq not in final_sequences:
                            final_sequences.append(seq)
        return final_sequences

    # all parent subsets, merge sequences
    def _get_sequences_by_level_3(self, parent_groups: list, ftn_idx):
        """
        consider all puarent subsets
        shortest sequences to represent parents
        merge sequence without topological sorting
        :param parent_groups:
        :param ftn_idx:
        :return:
        """

        final_sequences = []
        if len(parent_groups) == 0: return []

        # consider each parent individually
        parents = [p for p_list in parent_groups for p in p_list]
        parents = list(set(parents))
        for p_idx in parents:
            seq_gen = self._get_sequence_1_parent_considered(p_idx, ftn_idx)
            for seq in seq_gen:
                if seq not in final_sequences:
                    final_sequences.append(seq)

        # conside two or more parents
        if len(parent_groups) > 1:
            parent_subsets = []
            for i in range(1, len(parent_groups)):
                parent_combinations = utils.get_combination(parent_groups, i + 1)
                for com in parent_combinations:
                    parent_subsets.append(list(com))

            parent_sequences = []
            for p_subset in parent_subsets:
                p_sequences = self._get_parent_sequnces(p_subset)
                for p_seq in p_sequences:
                    seq_generated = self._merge_parent_sequence_list(p_seq, ftn_idx)
                    for seq in seq_generated:
                        if seq not in final_sequences:
                            final_sequences.append(seq)

        return final_sequences


    # randomly select parents, topological sorting,
    def _get_sequences_by_level_5(self, parent_groups: list, ftn_idx):
        """
        randomly select parents to get a parent subset
        get a specified number of parent subsets
        convet each parent sequence subset to one sequence

        topological sorting in sequence merging process
        :return:
        """
        collection_seq = []

        # select group subsets
        parent_subsets = []
        if len(parent_groups) == 1:  # consider parent individually
            if len(parent_groups[0]) > self.prt_subset_num_limit + 1:
                select = np.random.choice(parent_groups[0], size=self.prt_subset_num_limit, replace=False)
                parent_subsets = [[item] for item in select]
            else:
                parent_subsets = [[item] for item in parent_groups[0]]
        else:
            max_range = 2 ** len(parent_groups)
            if max_range > self.prt_subset_num_limit + 1:
                select = np.random.choice(list(range(1, max_range)), size=self.prt_subset_num_limit, replace=False)
            else:
                select = range(1, max_range)
            select_binary = [utils.get_binary(len(parent_groups), value) for value in select]
            for bin_list in select_binary:
                p_subset = []
                for i, bin_ele in enumerate(bin_list):
                    if bin_ele == 1:
                        # randomly select one parent from the group
                        p_subset.append(np.random.choice(parent_groups[i], size=1, replace=False)[0])
                if p_subset not in parent_subsets:
                    parent_subsets.append(p_subset)

        # for each group subset, randomly select one parent
        for p_subset in parent_subsets:
            if len(p_subset) == 1:
                seq_ = self._get_sequence_1_parent_considered(p_subset[0], ftn_idx)
                for seq in seq_:
                    if seq not in collection_seq:
                        collection_seq.append(seq)
            else:
                p_sequences = self._get_parent_sequnces(p_subset)
                for seq_list in p_sequences:
                    sequences = self._get_topological_sequences(seq_list, ftn_idx)
                    for seq in sequences:
                        if seq not in collection_seq:
                            collection_seq.append(seq)
        return collection_seq


    # get only one topological sequence from a sequence list
    def _get_topological_sequences(self, sequence_list: list, ftn_idx):
        """
        merge sequences, check if the merged sequence is in topological order
        if yes, return; otherwise, continue to
        note: convert sequences to a graph, 1) need to check dependency between each pair of nodes(one from one sequence, the other from another sequence)
        2) the graph can contain cycles,
        :param sequence_list:
        :param ftn_idx:
        :return:
        """
        collection_seq = []
        # number of possible sequence permutation
        seq_permutation = permutations(sequence_list)
        # convert each permutation to one sequence and check if it is in topological order
        # if yes, return, otherwise, continue the next permutation
        for seq_per in seq_permutation:
            # merge sequence
            seq_per = list(seq_per)
            if len(seq_per) <= 1: continue
            seq_merged = seq_per[0]
            for i in range(1, len(seq_per)):
                seq_merged = lists_merge.merge_two_list(seq_merged, seq_per[i])
            # seq_merged.append(ftn_idx)
            if not self._violate_topological_order(seq_merged):
                if len(seq_merged) >= 1:
                    if seq_merged not in collection_seq:
                        collection_seq.append(seq_merged)
                        # limit the number of sequences generated for each parent sequence list
                        if len(collection_seq) >= self.seq_num_limit: break

        final_sequences = []
        for seq in collection_seq:
            final = seq + [ftn_idx]
            final_sequences.append(final)

        return final_sequences

    def _violate_topological_order(self, sequence) -> bool:
        for i in range(len(sequence) - 1):
            parent_i = self.parents[sequence[i]] if sequence[i] in self.parents.keys() else []
            if len(parent_i) > 0:
                if len(list(set(parent_i).intersection(set(sequence[i + 1:])))) > 0:
                    return True
        return False

    # convert a parent subset to parent sequences
    def _get_parent_sequnces(self, parents: list):
        parent_sequences = []
        p_seq_num = []
        for p_element in parents:
            if p_element in self.valid_sequences_given_transformed.keys():
                p_seq_num.append(len(self.valid_sequences_given_transformed[p_element]['shortest']))
            else:
                p_seq_num.append(0)

        # if one parent does not have sequence, ignore this parent combination
        if p_seq_num.count(0) > 0:
            return []

        # some parent has multiple shortest sequences, so need to do combination
        p_seq_idx_list = [list(range(num)) for num in p_seq_num]
        p_seq_index_comb = [list(com) for com in it.product(*p_seq_idx_list)]
        for p_seq_index in p_seq_index_comb:
            # replace each parent with its shortest sequence
            # (remove 0: constructor is ignored.  reverse: so that parent itself is the last element in its shortest sequence )
            sequence_list = [
                self.valid_sequences_given_transformed[p_ele]['shortest'][index] \
                for p_ele, index in zip(parents, p_seq_index)]
            parent_sequences.append(sequence_list)

        return parent_sequences

    def _get_sequence_1_parent_considered(self, parent_idx: int, ftn_idx: int):
        collection_seq = []
        if parent_idx not in self.valid_sequences_given_transformed.keys(): return []
        p_sequences = self.valid_sequences_given_transformed[parent_idx]['sequences']
        for p_seq in p_sequences:
            if len(p_seq) == fdg.FDG_global.depth_all_ftns_reached:  # consider sequences of length fdg.FDG_global.depth_all_ftns_reached
                target_seq = p_seq + [ftn_idx]
                if target_seq not in collection_seq:
                    collection_seq.append(target_seq)
            # limit the number of sequences generated
            if len(collection_seq) >= self.seq_num_limit: break
        return collection_seq

    # ==================================================
    # ==================================================
    def generate_sequences(self):
        self.sequences_generated_cur = {}

        # delay the sequence generation for functions whose parents are also uncovered.
        if len(self.uncovered_ftn_idx) > 0:
            if self.flag_all_ftn_considered:
                return
            if len(self.uncovered_ftn_idx_waiting) > 0:
                self.uncovered_ftn_idx = self.uncovered_ftn_idx_waiting
                self.uncovered_ftn_idx_waiting = []

            ftn_to_generate_seq = []
            for ftn_idx in self.uncovered_ftn_idx:
                parents = self._get_parent(ftn_idx)
                if len(set(parents).intersection(set(self.uncovered_ftn_idx))) > 0:
                    self.uncovered_ftn_idx_waiting.append(ftn_idx)
                else:
                    ftn_to_generate_seq.append(ftn_idx)

            if len(ftn_to_generate_seq) == 0:  #
                self.uncovered_ftn_idx = self.uncovered_ftn_idx_waiting
                self.uncovered_ftn_idx_waiting = []
                self.flag_all_ftn_considered = True
            else:
                self.uncovered_ftn_idx = ftn_to_generate_seq
                if len(self.uncovered_ftn_idx_waiting) == 0:
                    self.flag_all_ftn_considered = True
        else:
            return  # no need to generate sequence

        # ==================================
        # get all sequences for each uncovered function
        for ftn_idx in self.uncovered_ftn_idx:
            # get labels and parents
            l_p_dict = self._get_label_parent(ftn_idx)

            if len(l_p_dict) == 0:
                self.ftn_no_sequences.append(ftn_idx)
                continue

            parent_groups = [values for values in l_p_dict.values() if len(values) > 0]

            all_sequences_ftn = []
            if fdg.FDG_global.control_level in [2]:
                all_sequences_ftn = self._get_sequences_by_level_2(parent_groups, ftn_idx)
            elif fdg.FDG_global.control_level in [3]:
                all_sequences_ftn = self._get_sequences_by_level_3(parent_groups, ftn_idx)
            elif fdg.FDG_global.control_level == 5:
                all_sequences_ftn = self._get_sequences_by_level_5(parent_groups, ftn_idx)


            if len(all_sequences_ftn) > 0:
                self.sequences_generated_cur[ftn_idx] = sorted(all_sequences_ftn, key=len)
            else:
                self.ftn_no_sequences.append(ftn_idx)

        if len(self.sequences_generated_cur.keys()) == 0:
            return
        self.sequences_generated.append(self.sequences_generated_cur)

        # use an 2d array to indicate which sequences are assigned
        ftn_list = []
        ftn_seq_num = []
        for ftn_idx, sequences in self.sequences_generated_cur.items():
            ftn_list.append(ftn_idx)
            ftn_seq_num.append(len(sequences))

        num_ftn = len(ftn_list)
        max_seq_num = max(ftn_seq_num)
        # create a matrix to register all sequences for each uncovered function
        self.assignment_sequence = np.zeros([max_seq_num, num_ftn])
        for idx, ftn_idx in enumerate(ftn_list):
            self.ftn_idx_to_column_idx[ftn_idx] = idx
            self.column_idx_to_ftn_idx[idx] = ftn_idx
            self.assignment_sequence[:, idx][0:ftn_seq_num[idx]] = 1
        return

    def get_one_sequence(self, ftn_not_covered: list) -> list:
        sequences = []
        if len(self.assignment_sequence) > 0:
            # update self.assignment_sequence
            for ftn_idx in self.uncovered_ftn_idx:
                if ftn_idx not in ftn_not_covered:
                    # unmark all its unassigned sequences
                    if ftn_idx in self.ftn_idx_to_column_idx.keys():
                        self.assignment_sequence[:, self.ftn_idx_to_column_idx[ftn_idx]] = 0

            # there are still generated sequences not assigned yet
            if 1 in self.assignment_sequence:
                # get sequences, the package size is 1
                sequences = self.assign_mark_a_sequence(1)[0]
                return sequences

        # update valid_sequences_given_transformed by adding valid sequences from the second phase
        valid_sequences = [item.split(',') for item in self.valid_sequences_given]
        valid_seq_dict_temp = {}
        for seq in valid_sequences:
            seq = [int(num) for num in seq]
            if seq[-1] not in valid_seq_dict_temp.keys():
                valid_seq_dict_temp[seq[-1]] = [seq]
            else:
                valid_seq_dict_temp[seq[-1]] += [seq]
        for key, value in valid_seq_dict_temp.items():
            if key in self.valid_seq_dict.keys():
                seq_list = self.valid_seq_dict[key] + value
                self.valid_sequences_given_transformed[key] = self._valid_sequence_transform(seq_list)
            else:
                self.valid_sequences_given_transformed[key] = self._valid_sequence_transform(value)

        # generate and assigne sequences
        self.generate_sequences()
        if len(self.sequences_generated_cur) == 0:
            return []
        sequences = self.assign_mark_a_sequence(1)[0]
        return sequences

    def assign_mark_a_sequence(self, package_size: int):

        indices = np.where(self.assignment_sequence == 1)
        indices_list = [(x, y) for x, y in zip(indices[0], indices[1])]
        sequences = []
        if len(indices_list) > 0:
            # get a list of sequences
            package_indices = indices_list[0:package_size]
            for (seq_idx, col_idx) in package_indices:
                # mark assigned sequences 0
                self.assignment_sequence[seq_idx, col_idx] = 0
                # get the sequence
                ftn_idx = self.column_idx_to_ftn_idx[col_idx]
                seq = self.sequences_generated_cur[ftn_idx][seq_idx]
                sequences.append(seq)
        return sequences


def _merge_sequences(nested_list: list):
    '''
    the prefix of the first sequence is not fixed
    :param nested_list:
    :return:
    '''
    ele_num = len(nested_list)
    if ele_num == 1: return []

    # merge sequence
    merge_seq = nested_list[0]

    for i in range(1, ele_num):
        merge_seq = lists_merge.merge_two_list(merge_seq, nested_list[i])

    return [merge_seq]


if __name__ == '__main__':
    # # ftn_info=Function_info('/home/wei/PycharmProjects/Contracts/_wei/Crowdsale.sol', 'Crowdsale')
    # ftn_info = Function_info('/home/wei/PycharmProjects/Contracts/_wei/HoloToken.sol', 'HoloToken')
    # # ftn_info = Function_info('/media/sf___share_vms/__contracts_1818/EtherBox.sol', 'EtherBox')
    #
    # function_dict = ftn_info.functions_dict_slither()
    #
    # fdg_object = FDG(function_dict)
    # # valid_sequence = {6: [[6], [5, 6]], 2: [[2]], 5: [[5]], 1: [[1], [1, 1], [5, 1]]}
    # valid_sequence={13: {'sequences': [[13], [2, 13], [2, 2, 13]], 'seq_num': 3, 'shortest': [[13]], 'shortest_depth': 1}, 4: {'sequences': [[4]], 'seq_num': 1, 'shortest': [[4]], 'shortest_depth': 1}, 10: {'sequences': [[10], [2, 10], [2, 2, 10]], 'seq_num': 3, 'shortest': [[10]], 'shortest_depth': 1}, 7: {'sequences': [[7]], 'seq_num': 1, 'shortest': [[7]], 'shortest_depth': 1}, 2: {'sequences': [[2], [2, 2], [2, 2, 2]], 'seq_num': 3, 'shortest': [[2]], 'shortest_depth': 1}, 9: {'sequences': [[9]], 'seq_num': 1, 'shortest': [[9]], 'shortest_depth': 1}, 8: {'sequences': [[8]], 'seq_num': 1, 'shortest': [[8]], 'shortest_depth': 1}, 12: {'sequences': [[10, 12], [2, 10, 12]], 'seq_num': 2, 'shortest': [[10, 12]], 'shortest_depth': 2}, 11: {'sequences': [[10, 11], [2, 10, 11], [10, 11, 11]], 'seq_num': 3, 'shortest': [[10, 11]], 'shortest_depth': 2}, 6: {'sequences': [[10, 12, 6]], 'seq_num': 1, 'shortest': [[10, 12, 6]], 'shortest_depth': 3}, 3: {'sequences': [[10, 12, 3]], 'seq_num': 1, 'shortest': [[10, 12, 3]], 'shortest_depth': 3}, 5: {'sequences': [[10, 12, 5]], 'seq_num': 1, 'shortest': [[10, 12, 5]], 'shortest_depth': 3}}
    # seq_object = Sequence(fdg_object, [3,4], valid_sequence, 5)
    # fdg.FDG_global.control_level=2
    # fdg_object.depth_limit=2
    # seq_object.generate_sequences()
    # print(f'sequence={seq_object.generated_sequences}')

    #
    # print(np.random.choice([1,2,3,4],size=2))
    # selection=[]
    # targets=[2,4,5,7,8]
    # for i in range(6):
    #     selection=[]
    #     for i in range(5):
    #         selection.append(np.random.choice([True,False]))
    #
    #     print(f'randomly choose: {selection}')
    #     print(f'randomly choose: {list(np.array(targets)[selection])}')
    #
    # index = list(range(10))
    # chosen_index = np.random.choice(index,5,replace=False)
    # print(index)
    # print(chosen_index)
    #
    #
    # holoToken_generated_sequences=[[[1, 10], 12, 3, 5, 11, 13, 14], [[1, 10], 12, 3, 5, 13, 11, 14], [[1, 10], 12, 3, 11, 5, 13, 14], [[1, 10], 12, 3, 11, 13, 5, 14], [[1, 10], 12, 3, 13, 5, 11, 14], [[1, 10], 12, 3, 13, 11, 5, 14], [[1, 10], 12, 5, 3, 11, 13, 14], [[1, 10], 12, 5, 3, 13, 11, 14], [[1, 10], 12, 5, 11, 3, 13, 14], [[1, 10], 12, 5, 11, 13, 3, 14], [[1, 10], 12, 5, 13, 3, 11, 14], [[1, 10], 12, 5, 13, 11, 3, 14], [[1, 10], 11, 12, 3, 5, 13, 14], [[1, 10], 11, 12, 3, 13, 5, 14], [[1, 10], 11, 12, 5, 3, 13, 14], [[1, 10], 11, 12, 5, 13, 3, 14], [[1, 10], 11, 13, 12, 3, 5, 14], [[1, 10], 11, 13, 12, 5, 3, 14], [[1, 13], 10, 12, 3, 5, 11, 14], [[1, 13], 10, 12, 3, 11, 5, 14], [[1, 13], 10, 12, 5, 3, 11, 14], [[1, 13], 10, 12, 5, 11, 3, 14], [[1, 13], 10, 11, 12, 3, 5, 14], [[1, 13], 10, 11, 12, 5, 3, 14]]

    # a=[1,2,3,4]
    # re=np.random.choice(a,size=4, replace=False)
    # print(list(range(1,3)))
    #
    # a=[[1],[],[2,3]]
    # b=[i for i in a if len(i)>0]
    # print(b)

    test = {"2,3": 1, "3,4": 2, "4,3": 3}
    keys = list(test.keys())
    keys = [item.split(',') for item in keys]
    re = {}
    for item in keys:
        item = [int(it) for it in item]
        if item[-1] not in re.keys():
            re[item[-1]] = [item]
        else:
            re[item[-1]] += [item]
    print(keys)
    print(re)

    dict_1={'1':2,"2":3,"3":4}
    dict_2={'1':'a',"4":"b","3":"c"}



    for i in range(10):
        if str(i) in set(dict_1.keys()).union(set(dict_2.keys())) :
            print(f'{i} in either dict')

    A=[1,1,2,3]
    B=[2,3,4]
    for i in range(10):
        if i in (A and B):
            print(i)
    print('----')
    for i in range(10):
        if i in A:
            print(i)
    print('----')
    for i in range(10):
        if i in B:
            print(i)
