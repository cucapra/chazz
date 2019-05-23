HOST_SRCS := run_manycore_program.c
HOST_TARGET := host
DEVICE_SRCS := main.c
DEVICE_TARGET := main.riscv


# Main targets.

.PHONY: all clean run

all: $(DEVICE_TARGET) $(HOST_TARGET)

clean:
	rm -rf *.o $(HOST_TARGET) $(DEVICE_TARGET)

run: all
	sudo ./$(HOST_TARGET) ./$(DEVICE_TARGET)


# Build host code with the "normal" compiler.

HOST_OBJS := $(HOST_SRCS:.c=.o)
HOST_CFLAGS := -std=c11 -lbsg_manycore_runtime
HOST_CC := cc
HOST_HEADER := f1_helper.h

$(HOST_TARGET): $(HOST_OBJS)
	$(HOST_CC) $(HOST_CFLAGS) $^ -o $@

$(HOST_OBJS): %.o: %.c $(HOST_HEADER)
	$(HOST_CC) $(HOST_CFLAGS) -c $< -o $@


# Include bsg_manycore Make infrastructure.

bsg_tiles_X := 4
bsg_tiles_Y := 3

BSG_MANYCORE_DIR := $(wildcard /home/centos/bsg_bladerunner/bsg_manycore_*)
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.dimensions
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.paths
include $(BSG_MANYCORE_DIR)/software/mk/Makefile.builddefs


# Build device binary.

DEVICE_OBJS := $(DEVICE_SRCS:.c=.o)

$(DEVICE_TARGET): $(DEVICE_OBJS) $(BSG_MANYCORE_LIB_OBJS)
	$(RISCV_LINK) $(RISCV_LINK_OPTS) $^ -o $@

$(OBJECT_FILES): %.o: %.c
	$(RISCV_GCC) $(RISCV_GCC_OPTS) $(OPT_LEVEL) $(spmd_defs) -c $< -o $@
