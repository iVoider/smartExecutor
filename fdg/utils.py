import itertools as it
import numpy as np

def random_select(sequences: list, num_selected: int):
    if len(sequences)>num_selected:
        select = np.random.choice(range(len(sequences)), size=num_selected, replace=False)
        return [sequences[idx] for idx in select]
    else: return sequences


def get_combination(list_for_comb,comb_length:int):
    """
    :param list_for_comb: [[1,4], [2,6],[5]]
    :param comb_length: 2 (two elements in a combination)
    :return: [(1, 2), (1, 6), (4, 2), (4, 6), (1, 5), (4, 5), (2, 5), (6, 5)]
    """
    com_re = []
    # do combination with length
    num_groups = len(list_for_comb)
    if num_groups<comb_length:return []

    # get group combinations
    com_groups = it.combinations(list_for_comb, comb_length)

    for groups in com_groups:
        com_re +=it.product(*list(groups))

    return com_re

def get_combination_for_a_list(list_for_comb,comb_length:int):
    re=[]
    if comb_length==1:
        re=[[item] for item in list_for_comb]
        return re
    for item in it.combinations(list_for_comb, comb_length):
        re.append(list(item))
    return re


def get_binary(length:int,number:int):
    bin_list=[]
    bin_str=bin(number)

    bin_list=[int(bin_str[i]) for i in range(2,len(bin_str))]
    if length>len(bin_list):
        extra=[0 for i in range(length -len(bin_list))]
        bin_list=extra+bin_list
    return bin_list



if __name__ == '__main__':
    import numpy as np
    print(get_binary(7,16))
    print(get_binary(6,16))
    print(np.random.choice(range(10), size=2, replace=False))
    print(get_combination_for_a_list([1,2,3],3))
    print(get_combination([["1","2"], ["b"]], 2))

    sv1_seq_indices = range(2)
    sv2_seq_indices = range(1)
    sv3_seq_indices = range(2)
    comb_indices = get_combination([sv1_seq_indices, sv2_seq_indices,sv3_seq_indices], 3)
    print(comb_indices)



