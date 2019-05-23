.PHONY: all clean run

all: main.riscv host

clean:
	rm -rf *.o host *.riscv

run: all
	sudo ./host ./main.riscv


# Build host code with the "normal" compiler.

HOST_SRCS := run_manycore_program.c
HOST_OBJS := $(HOST_SRCS:.c=.o)
CFLAGS := -std=c11 -lbsg_manycore_runtime
HOST_TARGET := host

$(HOST_TARGET): $(OBJS)
	cc $^ $(CFLAGS) -o $@

$(HOST_OBJS): %.o: %.c
	cc $(CFLAGS) -c -o $@ $<


# Set up bsg_manycore Make infrastructure.

BSG_TILES_X := 4
BSG_TILES_Y := 4
BSG_USEFUL_TILES_Y := 3

# Network.
bsg_global_X = $(BSG_TILES_X)
bsg_global_Y = $(BSG_TILES_Y)

# Tile group.
bsg_tiles_org_X = 1
bsg_tiles_org_Y = 1

# Group size.
bsg_tiles_X = $(BSG_TILES_X)
bsg_tiles_Y = $(BSG_USEFUL_TILES_Y)

# FPU option.
BSG_FPU_OP = 0

BSG_MANYCORE_DIR := $(wildcard /home/centos/bsg_bladerunner/bsg_manycore_*)
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.dimensions
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.paths
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.builddefs
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.filelist


# Build device binary.

OBJECT_FILES := main.o bsg_set_tile_x_y.o bsg_printf.o
TARGET := main

$(TARGET).riscv: $(OBJECT_FILES) $(SPMD_COMMON_OBJECTS) $(BSG_MANYCORE_DIR)/software/spmd/common/crt.o
	$(RISCV_LINK) $(OBJECT_FILES) $(SPMD_COMMON_OBJECTS) -o $@ $(RISCV_LINK_OPTS)

$(OBJECT_FILES): %.o: %.c
	$(RISCV_GCC) $(RISCV_GCC_OPTS) $(OPT_LEVEL) $(spmd_defs) -c $(INCS) $< -o $@
