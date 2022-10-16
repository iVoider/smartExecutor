#---------------------------------------------------
# provide them to FDG_pruner for FDG building
global solidity_path # the path of the solidity file containing the target contract
global contract  # the name of the target contract


# set the number of interations for the symbolic execution engine
global transaction_count
transaction_count=100

# set the coverage threshold so that the target function will be not considered once its coverage reaches this threshold
global function_coverage_threshold
function_coverage_threshold=100


# the depth limit for phase 1
global phase1_depth_limit
phase1_depth_limit=2


# indicate if Phase 1 explores all possible sequences
# 0: no; 1: yes
global phase1_execute_all_sequences
phase1_execute_all_sequences=0

# indicate if Phase 2 should be included
# 1: means include phase 2;
# 0 or others: does not include phase 2;
global phase2_include
phase2_include=1

# indicate which method of sequence generation is used
# not available now
global phase2_method_select
phase2_method_select=0

# set the number of sequences generated for a target function
# -1: no limit
global seq_num_limit
seq_num_limit=-1

# set the max length of a generated sequence
seq_len_limit=5 #



#---------------------------------------------------
# used by the FunctionCoverage module to calculate coverage for the target function
global target_bytecode
target_bytecode=''

# get instruction indices for each function (from soliditycontract)
global ftns_instr_indices
ftns_instr_indices={}


#---------------------------------------------------
# indicate if the coverage of functions will be printed out
# 1: yes; 0 or others: no
global print_function_coverage
print_function_coverage=0


#---------------------------------------------------
# level (in terms of the read of state variables):
# 0: all state variables read
# 1: state variables read in conditions
global level_phase1
level_phase1=0
global level_phase2
level_phase2=1

#---------------------------------------------------
# map integer values to the types of state variables
global primitive_index
primitive_index=2

global non_primitive_index
non_primitive_index=1



#===================================
# support executing sequences directly
global sequences
sequences=''

