#define _BSD_SOURCE
#define _XOPEN_SOURCE 500

#include <bsg_manycore_loader.h>
#include <bsg_manycore_cuda.h>
#include <stdlib.h>
#include <assert.h>

// 4 x 4 - 4 ( the 1st row is in charge of io ) 
#define X1 0
#define Y1 1
#define X2 4
#define Y2 4
#define NUM_TILES (X2 - X1) * (Y2 - Y1)

void print_vector(int* v, int start, int length) {
  for (int i = start; i < start + length; i++) {
    int val = v[i];
    if (i == start) {
        printf("(%d, ", val);
        fflush(stdout);
    }
    else if (i == start + length - 1) {
        printf(" %d)\n", val);
        fflush(stdout);
    }
    else {
        printf("%d, ", val);
        fflush(stdout);
    }
  }
}

void* sym_addr(hb_mc_device_t device, const char *name) {
  hb_mc_eva_t eva;
  int err = hb_mc_loader_symbol_to_eva(device.program->bin,
      device.program->bin_size, name, &eva);
  if (err != HB_MC_SUCCESS) {
    printf("symbol lookup failed!");
  }
  return (void*)((intptr_t)eva);

}

int main(int argc, char *argv[]) {
  assert(argc == 2);
  char *manycore_program = argv[1];

  // Initialize the device.
  hb_mc_device_t device;
  hb_mc_dimension_t mesh_dim = { .x = 4, .y = 3 };
  int err = hb_mc_device_init(&device, "example", 0, mesh_dim);
  if (err != HB_MC_SUCCESS) {
    printf("initialization failed\n");
    return err;
  }

  // Load the SPMD program in each core.
  err = hb_mc_device_program_init(&device, manycore_program,
          "default_allocator", 0);
  if (err != HB_MC_SUCCESS) {
    printf("program loading failed\n");
    return err;
  }

  // Define randomly generated vectors A, B,
  // with entries in [0, 100]
  int dim = 120;
  int *h_src0 = (int*)malloc(dim * sizeof(int));
  for(int i = 0; i < dim; i++) {
    h_src0[i] = rand() % 100;
  }
  int *h_src1 = (int*)malloc(dim * sizeof(int));
  for(int i = 0; i < dim; i++) {
    h_src1[i] = rand() % 100;
  }

  // Print generated vectors A, B
  printf("Input vectors: \n");
  printf("A = ");
  print_vector(h_src0, 0, dim);

  printf("B = ");
  print_vector(h_src1, 0, dim);

  // Load slice of vectors A, B to each tile
  int num_cores = (X2 - X1) * (Y2 - Y1);
  int dim_per_core = dim / num_cores;
  for (int y = Y1; y < Y2; y++) {
    for (int x = X1; x < X2; x++) {
      // This offset slices vectors across cores
      // in column-major order
      int offset = (y-Y1) * (X2-X1) * dim_per_core +
                   (x-X1) * dim_per_core;


      err = hb_mc_device_memcpy(&device, sym_addr(device, "g_src0"),
          (void*)(h_src0 + offset), dim_per_core * sizeof(int),
          hb_mc_memcpy_to_device);
      if (err != HB_MC_SUCCESS) {
        printf("memcpy failed");
        return err;
      }

      err = hb_mc_device_memcpy(&device, sym_addr(device, "g_src1"),
          (void*)(h_src1 + offset), dim_per_core * sizeof(int),
          hb_mc_memcpy_to_device);
      if (err != HB_MC_SUCCESS) {
        printf("memcpy failed");
        return err;
      }

      // print out slices sent to core (x, y)
      printf("Slice of vector A sent to core (%d, %d) = ", x, y);
      print_vector(h_src0, offset, dim_per_core);

      printf("Slice of vector B sent to core (%d, %d) = ", x, y);
      print_vector(h_src1, offset, dim_per_core);
    }
  }

  // Initialize the grid. (Adrian doesn't really understand what this step is
  // for or what a "tile group" or a "grid" really even is).
  hb_mc_dimension_t tg_dim = { .x = 4, .y = 3 };
  hb_mc_dimension_t grid_dim = { .x = 1, .y = 1 };
  err = hb_mc_grid_init(&device, grid_dim, tg_dim, "vvadd_entry", 0, NULL);
  if (err != HB_MC_SUCCESS) {
    printf("grid init failed\n");
    return err;
  }

  // Run the program.
  err = hb_mc_device_tile_groups_execute(&device);
  if (err != HB_MC_SUCCESS) {
    printf("execute failed\n");
    return err;
  }

  // Collect results from each tile
  int *h_dest = (int*)malloc(dim * sizeof(int));
  for (int y = Y1; y < Y2; y++) {
    for (int x = X1; x < X2; x++) {
      int offset = (y-Y1)*(X2-X1)*dim_per_core + (x-X1) * dim_per_core;
      err = hb_mc_device_memcpy(&device, sym_addr(device, "g_dest"),
          (void*)(h_dest + offset), dim_per_core * sizeof(int),
          hb_mc_memcpy_to_host);

      // print out results generated by core (x, y)
      printf("Output at core (%d, %d) = ", x, y);
      print_vector(h_dest, offset, dim_per_core);
    }
  }

  // Verify correctness of results
  int success = 1;
  for (int i = 0; i < dim; i++) {
    int correct_val = h_src0[i] + h_src1[i];
    if (h_dest[i] != correct_val) {
      printf("\nLOGIC ERROR: expected %d at index %d, got %d\n", 2*i, i, h_dest[i]);
      printf("\n");
      fflush(stdout);
      success = 0;
    }
  }
  if(success) {
    printf("VVADD yields correct answer.\n");
    printf("\n");
    fflush(stdout);
  }

  // cleanup host
  return 0;
}
