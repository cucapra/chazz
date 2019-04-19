#ifndef BSG_MANYCORE_ELF_H
#define BSG_MANYCORE_ELF 

#ifdef __cplusplus 
extern "C" {
#endif
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <getopt.h>
#include <stdint.h>
#include <alloca.h>
#include <inttypes.h>
#include <elf.h>
#ifndef COSIM
#include <bsg_manycore_driver.h>
#else
#include "bsg_manycore_driver.h"
#endif
typedef uint32_t eva_t;
int symbol_to_eva(const char *fname, const char *sym_name, eva_t *eva);
#ifdef __cplusplus
}
#endif

#endif
