
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
        if fdg.FDG_global.phase2_method_select==0:
            sequences_paper = self.generate_sequences_paper(ftn_idx)
        elif fdg.FDG_global.phase2_method_select==1:
            sequences_paper = self.generate_sequences_paper_1(ftn_idx)
        elif fdg.FDG_global.phase2_method_select==2:
            sequences_paper = self.generate_sequences_paper_2(ftn_idx)
        elif fdg.FDG_global.phase2_method_select==3:
            sequences_paper = self.generate_sequences_paper_3(ftn_idx)
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

    def generate_sequences_paper(self, ftn_idx: int) -> list:
        """
        get parent combinations
        one combination-> one sequence
        :param ftn_idx:
        :return:
        """
        sv_parents = self.FDG.get_parents(ftn_idx)
        if len(sv_parents) == 0: return []

        sv_list = list(sv_parents.keys())
        # sv_list =[2,3,4]


        generated_sequences = []  # to save the  generated sequences
        sv_combs = []
        for length in range(1, len(sv_list) + 1):
            sv_combs += utils.get_combination_for_a_list(sv_list, length)
        for sv_comb in sv_combs:
            if len(sv_comb) == 1:
                if isinstance(sv_parents, dict):
                    sequences = self.parent_sequences_write_one_SV(ftn_idx, sv_parents[sv_comb[0]], -1,
                                                                   self.phase1_depth)
                    for seq in sequences:
                        if seq not in generated_sequences:
                            generated_sequences.append(seq)
                else:
                    assert False, "data type error"
                continue

            # replace each sv with the corresponding parents
            sv_comb_parents = [sv_parents[sv] for sv in sv_comb]
            parent_combs = utils.get_combination(sv_comb_parents, len(sv_comb))
            for parent_comb in parent_combs:
                parent_comb = list(set(parent_comb))
                if len(parent_comb) < len(sv_comb): continue
                parent_sequence_list = []
                flag_comb = True
                for parent in parent_comb:
                    parent_seq = self.sequenceAndState.get_n_shortest_state_changing_sequences_for_a_function(parent, 1)
                    if len(parent_seq) == 0:
                        flag_comb = False
                        break  # if thre is one parent that does not have a parent sequence, ignore this parent combination
                    parent_sequence_list.append(parent_seq[0])
                if flag_comb:
                    generate_seq,_ = merge_sequences(parent_sequence_list, ftn_idx, self.FDG.graph_dict)
                    if generate_seq not in generated_sequences:
                        generated_sequences.append(generate_seq)

        return generated_sequences

    def _get_a_topological_sequence_0(self,ftn_idx:int, sequences:list)->list:
        """
        get a topological sequence from multiple sequences;
        start with the constructor;
        end with the target function (ftn_idx);

        based on function indices
        :param sequences:
        :return: a sequence, each element is an index
        """
        def get_graph(sequences: list,ftn_idx:int)->dict:
            """
            build a graph starting with the constructor and ending with self.ftn_idx
            :param sequences:
            :return:
            """
            graph = {}
            graph[0] = []
            graph[ftn_idx]=[]
            for seq in sequences:
                if len(seq)==0:continue
                if len(seq) == 1:
                    if seq[0] not in graph[0]: # connect the start node with the first node of the sequence
                        graph[0].append(seq[0])
                    if seq[0] not in graph.keys(): # connect the node with target node
                        graph[seq[0]] = [ftn_idx]
                    else:
                        if ftn_idx not in graph[seq[0]]:
                            graph[seq[0]] += [ftn_idx]
                else:
                    ftn_start = seq[0]
                    # add the edge between the constructor to the first function in the sequence
                    if ftn_start not in graph[0]:
                        graph[0].append(ftn_start)

                    # add the edge based on the sequence, each consecutive two functions has an edge
                    for ftn in seq[1:]:
                        if ftn_start not in graph.keys():
                            graph[ftn_start] = [ftn]
                        else:
                            if ftn not in graph[ftn_start]:
                                graph[ftn_start] += [ftn]
                        ftn_start = ftn

                    # add the edge between the last function in the sequence and the target function
                    assert (ftn_start == seq[-1])
                    if ftn_start not in graph.keys():
                        graph[ftn_start] = [ftn_idx]
                    else:
                        if ftn_idx not in graph[ftn_start]:
                            graph[ftn_start] += [ftn_idx]
            return graph

        # A recursive function used by topologicalSort
        def topologicalSortUtil(graph:dict,v,visited:dict, stack):
            # Mark the current node as visited.
            visited[v] = True
            # Recur for all the vertices adjacent to this vertex
            for i in graph[v]:
                if visited[i] == False:
                    topologicalSortUtil(graph,i, visited, stack)
            # Push current vertex to stack which stores result
            stack.insert(0, v)

        # compute the number of nodes
        all_nodes=[]
        for seq in sequences:
            all_nodes+=seq
        all_nodes= list(set(all_nodes))+[0,ftn_idx]
        num_nodes=len(all_nodes)

        # build the graph
        graph=get_graph(sequences,ftn_idx)

        # get the path
        # Mark all the vertices as not visited
        visited={}
        for node_idx in all_nodes:
            visited[node_idx]=False

        keys=list(visited.keys())

        stack = []
        # Call the recursive helper function to store Topological
        # Sort starting from all vertices one by one
        for i in visited.keys():
            if visited[i] == False:
                topologicalSortUtil(graph,i, visited, stack)
        return stack[1:]  # remove the first element: constructor

    def _get_a_topological_sequence(self, ftn_idx: int, sequences: list) -> list:
        """
        get a topological sequence from multiple sequences;
        start with the constructor;
        end with the target function (ftn_idx);

        based on function indices
        :param sequences:
        :return: a sequence, each element is an index
        """

        def get_graph(sequences: list, ftn_idx: int) -> dict:
            """
            build a graph starting with the constructor and ending with self.ftn_idx
            :param sequences:
            :return:
            """
            graph = {}
            graph[0] = []
            graph[ftn_idx] = []
            for seq in sequences:
                if len(seq) == 0: continue
                if len(seq) == 1:
                    if seq[0] not in graph[0]:  # connect the start node with the first node of the sequence
                        graph[0].append(seq[0])
                    if seq[0] not in graph.keys():  # connect the node with target node
                        graph[seq[0]] = [ftn_idx]
                    else:
                        if ftn_idx not in graph[seq[0]]:
                            graph[seq[0]] += [ftn_idx]
                else:
                    ftn_start = seq[0]
                    # add the edge between the constructor to the first function in the sequence
                    if ftn_start not in graph[0]:
                        graph[0].append(ftn_start)

                    # add the edge based on the sequence, each consecutive two functions has an edge
                    for ftn in seq[1:]:
                        if ftn_start not in graph.keys():
                            graph[ftn_start] = [ftn]
                        else:
                            if ftn not in graph[ftn_start]:
                                graph[ftn_start] += [ftn]
                        ftn_start = ftn

                    # add the edge between the last function in the sequence and the target function
                    assert (ftn_start == seq[-1])
                    if ftn_start not in graph.keys():
                        graph[ftn_start] = [ftn_idx]
                    else:
                        if ftn_idx not in graph[ftn_start]:
                            graph[ftn_start] += [ftn_idx]
            return graph

        # A recursive function used by topologicalSort
        def topologicalSortUtil(graph: dict, v, visited: dict, stack):
            # Mark the current node as visited.
            visited[v] = True
            # Recur for all the vertices adjacent to this vertex
            for i in graph[v]:
                if visited[i] == False:
                    topologicalSortUtil(graph, i, visited, stack)
            # Push current vertex to stack which stores result
            stack.insert(0, v)

        # compute the number of nodes
        all_nodes = []
        sequences_check = []
        flag_cycle = False
        mark = str(ftn_idx) + "_"
        for seq in sequences:
            seq_ = []
            for node in seq:
                if node == ftn_idx:
                    flag_cycle = True
                    node_ = mark
                else:
                    node_ = node
                seq_.append(node_)
                if node_ not in all_nodes:
                    all_nodes.append(node_)

            sequences_check.append(seq_)

        all_nodes += [0, ftn_idx]
        num_nodes = len(all_nodes)

        # build the graph
        graph = get_graph(sequences_check, ftn_idx)

        # get the path
        # Mark all the vertices as not visited
        visited = {}
        for node_idx in all_nodes:
            visited[node_idx] = False

        keys = list(visited.keys())

        stack = []
        # Call the recursive helper function to store Topological
        # Sort starting from all vertices one by one
        for i in visited.keys():
            if visited[i] == False:
                topologicalSortUtil(graph, i, visited, stack)
        final_seq = []
        if flag_cycle:
            for item in stack[1:]:
                if str(item).__eq__(mark):
                    final_seq.append(ftn_idx)
                else:
                    final_seq.append(item)
        else:
            final_seq = stack[1:]  # remove the first element: constructor(0)

        return final_seq

    def generate_sequences_paper(self,ftn_idx:int)->list:
        """
        get parent combinations
        one combination-> one sequence
        :param ftn_idx:
        :return:
        """
        sv_parents = self.FDG.get_parents(ftn_idx)
        if len(sv_parents) == 0: return []
        if ftn_idx==3:
            print(f'xxx')
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
                    generate_seq=self._get_a_topological_sequence(ftn_idx,parent_sequence_list)
                    if generate_seq not in generated_sequences:
                        generated_sequences.append(generate_seq)

        return generated_sequences

    def generate_sequences_paper_1(self, ftn_idx: int) -> list:
        """
        get parent combinations
        one combination-> one sequence
        generate sequences for functions that have no parents
        :param ftn_idx:
        :return:
        """
        sv_parents = self.FDG.get_parents(ftn_idx)
        if len(sv_parents) == 0:
            return self.generate_sequences_for_functions_without_parents(ftn_idx)

        sv_list = list(sv_parents.keys())
        # sv_list =[2,3,4]
        generated_sequences = []  # to save the  generated sequences
        sv_combs = []
        for length in range(1, len(sv_list) + 1):
            sv_combs += utils.get_combination_for_a_list(sv_list, length)
        for sv_comb in sv_combs:
            if len(sv_comb) == 1:
                if isinstance(sv_parents, dict):
                    sequences = self.parent_sequences_write_one_SV(ftn_idx, sv_parents[sv_comb[0]], -1,
                                                                   self.phase1_depth)
                    for seq in sequences:
                        if seq not in generated_sequences:
                            generated_sequences.append(seq)
                else:
                    assert False, "data type error"
                continue

            # replace each sv with the corresponding parents
            sv_comb_parents = [sv_parents[sv] for sv in sv_comb]
            parent_combs = utils.get_combination(sv_comb_parents, len(sv_comb))
            for parent_comb in parent_combs:
                parent_comb=list(set(parent_comb))
                if len(parent_comb)<len(sv_comb):continue
                parent_sequence_list = []
                flag_comb = True
                for parent in parent_comb:
                    parent_seq = self.sequenceAndState.get_n_shortest_state_changing_sequences_for_a_function(parent, 1)
                    if len(parent_seq) == 0:
                        flag_comb = False
                        break  # if thre is one parent that does not have a parent sequence, ignore this parent combination
                    parent_sequence_list.append(parent_seq[0])
                if flag_comb:
                    generate_seq = self._get_a_topological_sequence(ftn_idx, parent_sequence_list)
                    if generate_seq not in generated_sequences:
                        generated_sequences.append(generate_seq)

        return generated_sequences

    def generate_sequences_paper_2(self, ftn_idx: int) -> list:
        """
        get parent combinations
        one combination-> multiple sequences

        :param ftn_idx:
        :return:
        """
        sv_parents = self.FDG.get_parents(ftn_idx)
        if len(sv_parents) == 0: return []

        sv_list = list(sv_parents.keys())
        # sv_list =[2,3,4]
        generated_sequences = []  # to save the  generated sequences
        sv_combs = []
        for length in range(1, len(sv_list) + 1):
            sv_combs += utils.get_combination_for_a_list(sv_list, length)
        for sv_comb in sv_combs:
            if len(sv_comb) == 1:
                if isinstance(sv_parents, dict):
                    sequences = self.parent_sequences_write_one_SV(ftn_idx, sv_parents[sv_comb[0]], -1,
                                                                   self.phase1_depth)
                    for seq in sequences:
                        if seq not in generated_sequences:
                            generated_sequences.append(seq)
                else:
                    assert False, "data type error"
                continue

            # replace each sv with the corresponding parents
            sv_comb_parents = [sv_parents[sv] for sv in sv_comb]
            parent_combs = utils.get_combination(sv_comb_parents, len(sv_comb))
            for parent_comb in parent_combs:
                parent_comb = list(set(parent_comb))
                if len(parent_comb) < len(sv_comb): continue  # when a parent occurs more than once
                prt_seq_list = [self.sequenceAndState.get_state_changing_sequences(prt_idx) for prt_idx in parent_comb]
                # get parent sequence combination
                prt_seq_len_list = [list(range(len(prt_seq))) for prt_seq in prt_seq_list]
                prt_seq_idx_combs = utils.get_combination(prt_seq_len_list, len(sv_comb))
                for prt_seq_idx_comb in prt_seq_idx_combs:
                    # get parent sequence list
                    parent_seq_list = [prt_seq_list[prt_idx][prt_seq_idx] for prt_idx, prt_seq_idx in
                                       enumerate(prt_seq_idx_comb)]
                    # merge parent sequences in the parent sequence list
                    generate_seq = self._get_a_topological_sequence(ftn_idx, parent_seq_list)
                    if generate_seq not in generated_sequences:
                        generated_sequences.append(generate_seq)

        return generated_sequences

    def generate_sequences_paper_3(self, ftn_idx: int) -> list:
        """
        get parent combinations
        one combination-> multiple sequences
        generate sequences for functions that have no parents
        :param ftn_idx:
        :return:
        """
        sv_parents = self.FDG.get_parents(ftn_idx)
        if len(sv_parents) == 0:
            return self.generate_sequences_for_functions_without_parents(ftn_idx)

        sv_list = list(sv_parents.keys())
        # sv_list =[2,3,4]
        generated_sequences = []  # to save the  generated sequences
        sv_combs = []
        for length in range(1, len(sv_list) + 1):
            sv_combs += utils.get_combination_for_a_list(sv_list, length)
        for sv_comb in sv_combs:
            if len(sv_comb) == 1:
                if isinstance(sv_parents, dict):
                    sequences = self.parent_sequences_write_one_SV(ftn_idx, sv_parents[sv_comb[0]], -1,
                                                                   self.phase1_depth)
                    for seq in sequences:
                        if seq not in generated_sequences:
                            generated_sequences.append(seq)
                else:
                    assert False, "data type error"
                continue

            # replace each sv with the corresponding parents
            sv_comb_parents = [sv_parents[sv] for sv in sv_comb]
            parent_combs = utils.get_combination(sv_comb_parents, len(sv_comb))
            for parent_comb in parent_combs:
                parent_comb = list(set(parent_comb))
                if len(parent_comb) < len(sv_comb): continue  # when a parent occurs more than once
                prt_seq_list = [self.sequenceAndState.get_state_changing_sequences(prt_idx) for prt_idx in parent_comb]
                # get parent sequence combination
                prt_seq_len_list = [list(range(len(prt_seq))) for prt_seq in prt_seq_list]
                prt_seq_idx_combs = utils.get_combination(prt_seq_len_list, len(sv_comb))
                for prt_seq_idx_comb in prt_seq_idx_combs:
                    # get parent sequence list
                    parent_seq_list = [prt_seq_list[prt_idx][prt_seq_idx] for prt_idx, prt_seq_idx in
                                       enumerate(prt_seq_idx_comb)]
                    # merge parent sequences in the parent sequence list
                    generate_seq = self._get_a_topological_sequence(ftn_idx, parent_seq_list)
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

def get_a_topological_sequence(ftn_idx:int, sequences:list)->list:
    """
    get a topological sequence from multiple sequences;
    start with the constructor;
    end with the target function (ftn_idx);

    based on function indices
    :param sequences:
    :return: a sequence, each element is an index
    """
    def get_graph(sequences: list,ftn_idx:int)->dict:
        """
        build a graph starting with the constructor and ending with self.ftn_idx
        :param sequences:
        :return:
        """
        graph = {}
        graph[0] = []
        graph[ftn_idx]=[]
        for seq in sequences:
            if len(seq)==0:continue
            if len(seq) == 1:
                if seq[0] not in graph[0]: # connect the start node with the first node of the sequence
                    graph[0].append(seq[0])
                if seq[0] not in graph.keys(): # connect the node with target node
                    graph[seq[0]] = [ftn_idx]
                else:
                    if ftn_idx not in graph[seq[0]]:
                        graph[seq[0]] += [ftn_idx]
            else:
                ftn_start = seq[0]
                # add the edge between the constructor to the first function in the sequence
                if ftn_start not in graph[0]:
                    graph[0].append(ftn_start)

                # add the edge based on the sequence, each consecutive two functions has an edge
                for ftn in seq[1:]:
                    if ftn_start not in graph.keys():
                        graph[ftn_start] = [ftn]
                    else:
                        if ftn not in graph[ftn_start]:
                            graph[ftn_start] += [ftn]
                    ftn_start = ftn

                # add the edge between the last function in the sequence and the target function
                assert (ftn_start == seq[-1])
                if ftn_start not in graph.keys():
                    graph[ftn_start] = [ftn_idx]
                else:
                    if ftn_idx not in graph[ftn_start]:
                        graph[ftn_start] += [ftn_idx]
        return graph

    # A recursive function used by topologicalSort
    def topologicalSortUtil(graph:dict,v,visited:dict, stack):
        # Mark the current node as visited.
        visited[v] = True
        # Recur for all the vertices adjacent to this vertex
        for i in graph[v]:
            if visited[i] == False:
                topologicalSortUtil(graph,i, visited, stack)
        # Push current vertex to stack which stores result
        stack.insert(0, v)

    # compute the number of nodes
    all_nodes=[]
    sequences_check=[]
    flag_cycle=False
    mark=str(ftn_idx)+"_"
    for seq in sequences:
        seq_=[]
        for node in seq:
            if node ==ftn_idx:
                flag_cycle=True
                node_=mark
            else:
                node_=node
            seq_.append(node_)
            if node_ not in all_nodes:
                all_nodes.append(node_)

        sequences_check.append(seq_)

    all_nodes+=[0,ftn_idx]
    num_nodes=len(all_nodes)

    # build the graph
    graph=get_graph(sequences_check,ftn_idx)

    # get the path
    # Mark all the vertices as not visited
    visited={}
    for node_idx in all_nodes:
        visited[node_idx]=False

    keys=list(visited.keys())

    stack = []
    # Call the recursive helper function to store Topological
    # Sort starting from all vertices one by one
    for i in visited.keys():
        if visited[i] == False:
            topologicalSortUtil(graph,i, visited, stack)
    final_seq=[]
    if flag_cycle:
        for item in stack[1:]:
            if str(item).__eq__(mark):
                final_seq.append(ftn_idx)
            else:
                final_seq.append(item)
    else:
        final_seq=stack[1:] # remove the first element: constructor(0)

    return final_seq

if __name__=="__main__":

    print(get_a_topological_sequence(3,[[3,2],[3,5]]))
