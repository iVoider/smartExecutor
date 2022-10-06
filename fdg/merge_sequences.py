def get_graph(sequences: list, ftn_idx: int, all_edges: dict,all_nodes:list) -> dict:
    """
    build a graph starting with the constructor and ending with self.ftn_idx
    add missing edges between non-constructor functions
    :param sequences:
    :return:
    """
    graph = {}
    graph[0] = []  # the start node
    graph[ftn_idx] = []  # the end node

    for seq in sequences:
        if len(seq) == 0: continue
        ftn_start = seq[0]
        # add the edge between the start node to the first node in the sequence
        if ftn_start not in graph[0]:
            graph[0].append(ftn_start)

        # add the edge based on the sequence, each consecutive two nodes has an edge
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

        # add edges between nodes(not include the start node) that are not added based on all_edges and all_nodes
        for key,value in graph.items():
            if key==0: continue
            if key in all_edges.keys():
                children=value
                children_all=all_edges[key]
                for child in children_all:
                    if child in all_nodes and child not in value:
                        # find a missing edge and add it
                        children.append(child)
                graph[key]=children
    return graph

# traverse the graph
def graph_traversal_postorder_DFS(graph:dict,node,visited:dict, stack:list):
    # Mark the current node as visited.
    visited[node] = True
    # go to visit all child nodes for this node
    for child in graph[node]:
        if visited[child] == False:
            graph_traversal_postorder_DFS(graph,child, visited, stack)
    # after visiting all its child node, push the current node to the stack
    stack.insert(0, node)


# merge sequences
def merge_sequences(sequences:list,ftn_idx:int,all_edges:dict)->list:
    # check the sequences
    sequences_check,all_nodes,flag=check_sequences(sequences,ftn_idx)

    # build the graph
    graph = get_graph(sequences_check, ftn_idx, all_edges,all_nodes)


    # Mark all the vertices as not visited
    visited={}
    for node_idx in all_nodes:
        visited[node_idx]=False
    stack = []

    # Call the recursive helper function to sort from the start node 0
    graph_traversal_postorder_DFS(graph, 0, visited, stack)

    if flag:
        return check_merged_sequence(stack,ftn_idx),graph
    else: return stack[1:],graph



def check_sequences(sequences:list,ftn_idx:int):
    # check if the sequences contains fin_idx, if yes, replace with a differnt name.
    all_nodes = []
    sequences_check = []
    flag = False
    mark = str(ftn_idx) + "_"
    for seq in sequences:
        seq_ = []
        for node in seq:
            if node == ftn_idx:
                flag = True
                node_ = mark
            else:
                node_ = node
            seq_.append(node_)
            if node_ not in all_nodes:
                all_nodes.append(node_)
        sequences_check.append(seq_)
    all_nodes += [0, ftn_idx]
    return sequences_check,all_nodes,flag

def check_merged_sequence(sequence:list,ftn_idx:int):
    # get the final sequence
    final_seq = []
    mark=str(ftn_idx)+"_"
    for item in sequence[1:]:
        if str(item).__eq__(mark):
            final_seq.append(ftn_idx)
        else:
            final_seq.append(item)
    return final_seq

def test_merge_sequences():
    target=5
    sequences=[[1,2],[3]]
    all_edges={0:[1,2,3,5],1:[2],2:[3,5],3:[2,5]}
    seq,graph=merge_sequences(sequences,target,all_edges)
    print(f'graph={graph}')
    print(f'merged_seq={seq}')
    target = 5
    sequences = [[1, 2], [5, 3]]
    all_edges = {0: [1, 2, 3, 5], 1: [2], 2: [3, 5], 3: [2, 5]}
    seq,graph = merge_sequences(sequences, target, all_edges)
    print(f'graph={graph}')
    print(f'merged_seq={seq}')

def test_get_graph():
    target=5
    sequences=[[1,2],[3]]
    all_edges={0:[1,2,3,5],1:[2],2:[3,5],3:[2,5]}
    all_nodes=[0,1,2,3,5]
    graph=get_graph(sequences,target,all_edges, all_nodes)
    print(f'graph={graph}')
    print(f'all_nodes={all_nodes}')



if __name__=='__main__':
    test_get_graph()
    test_merge_sequences()
