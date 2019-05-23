export BSG_TILES_X=4
export BSG_TILES_Y=4 
# one less than bsg_tiles_y
export BSG_USEFUL_TILES_Y=3
#########################################################
# Network Configutaion
# If not configured, Will use default Values
#	bsg_global_X ?= $(bsg_tiles_X)
#	bsg_global_Y ?= $(bsg_tiles_Y)+1
bsg_global_X = $(BSG_TILES_X)
bsg_global_Y = $(BSG_TILES_Y)

#########################################################
#Tile group configuration
# this can be specified at runtime though!
# If not configured, Will use default Values
#	bsg_tiles_org_X ?= 0
#	bsg_tiles_org_Y ?= 1
bsg_tiles_org_X =1
bsg_tiles_org_Y =1

# group size, this cannot be specified at runtime! Oh no!
# Can we just set to max possible size and then not use all
# all of them?
# If not configured, Will use default Values
#	bsg_tiles_X ?= 2
#	bsg_tiles_Y ?= 2
bsg_tiles_X = $(BSG_TILES_X)
bsg_tiles_Y = $(BSG_USEFUL_TILES_Y)


all: main.riscv

# Rule to write processor execution logs. To be used after the
# verilog simulation.
#
# Redirects verilog standard output starting with "X<x_cord>_Y<y_cord>.pelog" 
# to a unique log file for each coordinate in the manycore. This can be useful 
# for a quick debug of processor or program running on it.
proc_exe_logs: X0_Y0.pelog X1_Y0.pelog

OBJECT_FILES=main.o bsg_set_tile_x_y.o bsg_printf.o

#include /home/centos/bsg_bladerunner/bsg_manycore_3903da0/software/spmd/Makefile.include
BSG_MANYCORE_DIR := $(wildcard /home/centos/bsg_bladerunner/bsg_manycore_*)
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.dimensions
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.paths
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.builddefs
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.filelist

#########################################################
#            FPU OPTION
#     The number of horizon node must be two and must 
#     be vanilla core 
BSG_FPU_OP=0

main.riscv: $(OBJECT_FILES) $(SPMD_COMMON_OBJECTS) $(BSG_MANYCORE_DIR)/software/spmd/common/crt.o
	$(RISCV_LINK) $(OBJECT_FILES) $(SPMD_COMMON_OBJECTS) -o $@ $(RISCV_LINK_OPTS)


main.o: Makefile

include $(BSG_MANYCORE_DIR)/software/mk/Makefile.tail_rules
