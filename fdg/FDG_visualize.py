import matplotlib as mpl
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
from matplotlib import gridspec

from fdg.FDG import FDG
import sys


def draw_FDG_w_edge_label(nodes_list,edges_dict,nodes_labels,colors_list,save_pdf):


    # get needed edge data from edges_label_dictt
    edges_list = []
    edges_label_dict = {}
    edges_label_list = []

    for key, value in edges_dict.items():
        # edges_list.append(tuple(map(str,key.split(','))) )
        edge_tuple = tuple(key.split(','))
        edges_list.append(edge_tuple)
        edges_label_dict[edge_tuple] = value
        edges_label_list.append(value)
    # # ValueError: dictionary update sequence element #0 has length 1; 2 is required
    # # The problem is here tuple(e) a single item in the tuple, wants two items tuple(item1, item2)


    # create graph, add nodes and edges
    G = nx.MultiDiGraph()
    G.add_nodes_from(nodes_list)
    G.add_edges_from(edges_list)

    # about positioning nodes for the graph
    # pos = nx.layout.spectral_layout(G)
    # pos = nx.layout.planar_layout(G)
    pos = nx.layout.circular_layout(G)
    # pos = nx.layout.spring_layout(G)
    # pos = nx.layout.shell_layout(G)

    # get an color for each node
    nodes_color_list = []
    # only the start node had a different color
    for item in nodes_list:
        if item == 'f0':
            nodes_color_list.append('crimson')
            continue
        nodes_color_list.append('wheat')

    # assign a color to each unique edge lable
    edges_labels_unique = list(set(edges_label_list))
    edges_label_color_dict = {}


    for i in range(len(edges_labels_unique)):
        edges_label_color_dict[edges_labels_unique[i]] = colors_list[i]

    # for edges in the Graph, edges are ordered by item1,item2 in the edge tuple(item1,item2)
    # so, the edge colors should be based on the order of edges in G not in edges_list
    edges_color_list = []
    for edge in G.edges():
        label = edges_label_dict.get(edge)
        edges_color_list.append(edges_label_color_dict.get(label))

        # fig, (ax1,ax2)=plt.subplots(nrows=1,ncols=2,figsize=(10,6))

    height=7
    # create a figure
    fig = plt.figure()
    # to change size of subplot's
    # set height of each subplot as 8
    fig.set_figheight(height)

    # set width of each subplot as 8
    fig.set_figwidth(12)

    # create grid for different subplots
    spec = gridspec.GridSpec(ncols=2, nrows=1,
                             width_ratios=[3, 1], wspace=0,
                             hspace=0)

    # # initializing x,y axis value
    # x = np.arange(0, 10, 0.1)
    # y = np.cos(x)

    # ax1 will take 0th position in
    # geometry(Grid we created for subplots),
    # as we defined the position as "spec[0]"
    ax1 = fig.add_subplot(spec[0])

    # ax2 will take 0th position in
    # geometry(Grid we created for subplots),
    # as we defined the position as "spec[1]"
    ax2 = fig.add_subplot(spec[1])

    # draw nodes
    h1=nodes = nx.draw(G, pos,ax=ax1, node_size=500, node_color=nodes_color_list, alpha=0.9,
                    labels={node: node for node in G.nodes()}, with_labels=True, font_color='black')

    # draw edges
    h2=nx.draw_networkx_edges(G, pos, ax=ax1,arrowstyle="->", arrowsize=20, edge_color=edges_color_list, width=2)

    # # draw edge labels
    # nx.draw_networkx_edge_labels(G, pos, edge_labels=edges_label_dict, font_color='black')

    # show the legend of edges
    ax2.text(0,0.9,"color  label (edge)", ha='left',fontweight='bold')
    def make_proxy(crl,mappable,**kwargs):
        return Line2D([0,1],[0,1], color=crl, **kwargs)
    edge_labels = ["{}".format(edges_label_dict.get(edge)) for (edge) in G.edges()]
    edge_labels=list(set(edge_labels))
    edge_colors=[edges_label_color_dict.get(label) for label in edge_labels]
    proxies=[make_proxy(clr,h2,lw=5) for clr in edge_colors]
    ax2.legend(proxies, edge_labels,loc='upper left',bbox_to_anchor=(0,0.9))

    y_index = 0.9 - 0.04 * (len(edge_labels) + 1)
    ax2.text(0, y_index, "node: function name", ha='left', fontweight='bold')
    # show legend: node--function name

    for index,ftn_name in enumerate(nodes_labels):
        y_index-=0.03
        ax2.text(0, y_index, "f"+str(index)+":  "+ftn_name, ha='left')


    ax2.set_axis_off()
    fig.tight_layout()
    if len(save_pdf)>0:
        plt.savefig(save_pdf)
    plt.show()

def draw_FDG_w_edge_label_node_label(functions_dict,nodes_list,edges_dict,colors_list):

    # get needed edge data from edges_label_dictt
    edges_list = []
    edges_label_dict = {}
    edges_label_list = []

    for key, value in edges_dict.items():
        # edges_list.append(tuple(map(str,key.split(','))) )
        edge_tuple = tuple(key.split(','))
        edges_list.append(edge_tuple)
        edges_label_dict[edge_tuple] = value
        edges_label_list.append(value)
    # # ValueError: dictionary update sequence element #0 has length 1; 2 is required
    # # The problem is here tuple(e) a single item in the tuple, wants two items tuple(item1, item2)


    # create graph, add nodes and edges
    G = nx.MultiDiGraph()
    G.add_nodes_from(nodes_list)
    G.add_edges_from(edges_list)

    # about positioning nodes for the graph
    # pos = nx.layout.spectral_layout(G)
    # pos = nx.layout.planar_layout(G)
    pos = nx.layout.circular_layout(G)
    # pos = nx.layout.spring_layout(G)

    # get an color for each node
    nodes_color_list = []
    # only the start node had a different color
    for item in nodes_list:
        if item == 'f0':
            nodes_color_list.append('crimson')
            continue
        nodes_color_list.append('wheat')

    # get node name
    nodes_name_dict={}
    for node in G.nodes:
        nodes_name_dict[node]=functions_dict.get(node)[0]

    # assign a color to each unique edge lable
    edges_labels_unique = list(set(edges_label_list))
    edges_label_color_dict = {}

    for i in range(len(edges_labels_unique)):
        edges_label_color_dict[edges_labels_unique[i]] = colors_list[i]

    # for edges in the Graph, edges are ordered by item1,item2 in the edge tuple(item1,item2)
    # so, the edge colors should be based on the order of edges in G not in edges_list
    edges_color_list = []
    for edge in G.edges():
        label = edges_label_dict.get(edge)
        edges_color_list.append(edges_label_color_dict.get(label))

    # draw nodes
    nodes = nx.draw(G, pos, node_size=5000, node_color=nodes_color_list, alpha=1,
                    labels={node: nodes_name_dict.get(node) for node in G.nodes()}, with_labels=True, font_color='black')

    # draw edges
    nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=20, edge_color=edges_color_list, width=2)

    # draw edge labels
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edges_label_dict, font_color='black')

    ax = plt.gca()
    ax.set_axis_off()

    plt.show()

def draw_FDG_wo_edge_label(nodes_list,edges_list):
    edges_list_1=[]
    for edge in edges_list:
        edge_tuple=tuple(str(edge).split(','))
        edges_list_1.append(edge_tuple)

    # create graph, add nodes and edges
    G = nx.MultiDiGraph()
    G.add_nodes_from(nodes_list)
    G.add_edges_from(edges_list_1)

    # about positioning nodes for the graph
    # pos = nx.layout.spectral_layout(G)
    # pos = nx.layout.planar_layout(G)
    pos = nx.layout.circular_layout(G)
    # pos = nx.layout.spring_layout(G)

    # get an color for each node
    nodes_color_list = []
    # only the start node had a different color
    for item in nodes_list:
        if item == 'f0':
            nodes_color_list.append('crimson')
            continue
        nodes_color_list.append('wheat')


    # draw nodes
    nodes = nx.draw(G, pos, node_size=500, node_color=nodes_color_list, alpha=0.9,
                    labels={node: node for node in G.nodes()}, with_labels=True, font_color='black',
                    arrowstyle="->", arrowsize=20,width=2
                    )

    ax = plt.gca()
    ax.set_axis_off()
    plt.show()

def draw_FDG_w_node_label(functions_dict,nodes_list,edges_dict):

    # get needed edge data from edges_label_dict
    edges_list = []
    for key, value in edges_dict.items():
        # edges_list.append(tuple(map(str,key.split(','))) )
        edge_tuple = tuple(key.split(','))
        edges_list.append(edge_tuple)

    # create graph, add nodes and edges
    G = nx.MultiDiGraph()
    G.add_nodes_from(nodes_list)
    G.add_edges_from(edges_list)

    # about positioning nodes for the graph
    # pos = nx.layout.spectral_layout(G)
    # pos = nx.layout.planar_layout(G)
    pos = nx.layout.circular_layout(G)
    # pos = nx.layout.spring_layout(G)

    # get an color for each node
    nodes_color_list = []
    # only the start node had a different color
    for item in nodes_list:
        if item == 'f0':
            nodes_color_list.append('crimson')
            continue
        nodes_color_list.append('wheat')

    # get node name
    nodes_name_dict={}
    for node in G.nodes:
        nodes_name_dict[node]=functions_dict.get(node)[0]

    # draw nodes
    nodes = nx.draw(G, pos, node_size=5000, node_color=nodes_color_list, alpha=0.9,
                    labels={node: nodes_name_dict.get(node) for node in G.nodes()}, with_labels=True, font_color='black',
                    arrowstyle="->", arrowsize=20,width=2
                    )

    ax = plt.gca()
    ax.set_axis_off()
    plt.show()


def get_nodes_edges_from_fdg(fdg:FDG):
    nodes=['f'+str(key) for key,_ in fdg.index_to_ftn.items()]
    edge_dict=fdg.edges
    nodes_labels=[0]*fdg.num_ftn
    for index, ftn in fdg.index_to_ftn.items():
        nodes_labels[index]=ftn
    nodes_labels[0]='constructor()'
    nodes_labels[1]='fallback()'



    return nodes,edge_dict,nodes_labels







