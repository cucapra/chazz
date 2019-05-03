#include "f1_helper.h"

// 4 x 4 - 4 ( the t p row, in charge of io ) 
#define X1 0
#define Y1 1
#define X2 4
#define Y2 4
#define NUM_TILES (X2 - X1) * (Y2 - Y1)

int main(int argc, char *argv[]) {
  assert(argc == 2);
  char *manycore_program = argv[1];
  
  uint8_t fd;
  if (hb_mc_init_host(&fd) != HB_MC_SUCCESS) {
    printf("failed to initialize host.\n");
    return 0;
  }
  
  int dim = 160;
  int *h_src1 = (int*)malloc(dim * sizeof(int));
  for(int i = 0; i < dim; i++) {
    h_src1[i] = i;
  }
  int *h_src0 = (int*)malloc(dim * sizeof(int));
  for(int i = 0; i < dim; i++) {
    h_src0[i] = i;
  }
   
  hammaLoadMultiple(fd, manycore_program, X1, Y1, X2, Y2);
    
  // do a data copy of the whole array to tile spads
  // NOTE -- must be done after loading the kernel to hammerblade
  for (int y = Y1; y < Y2; y++) {
    for (int x = X1; x < X2; x++) {
      hammaSymbolMemcpy(fd, x, y, manycore_program, "g_src1", (void*)h_src1, dim * sizeof(int), hostToDevice);
      hammaSymbolMemcpy(fd, x, y, manycore_program, "g_src0", (void*)h_src0, dim * sizeof(int), hostToDevice);
    }
  }

  // run all of the tiles
  hammaRunMultiple(fd, X1, Y1, X2, Y2);
    
  // TEMP -- everytile adds the whole array and we're just copying and check each the same
  int *h_dest = (int*)malloc(dim * sizeof(int));

  for (int y = Y1; y < Y2; y++) {
    for (int x = X1; x < X2; x++) {
      hammaSymbolMemcpy(fd, x, y, manycore_program, "g_dest", (void*)h_dest, dim * sizeof(int), deviceToHost);

      for (int i = 0; i < dim; i++) {
	if (h_dest[i] != 2 * i) {
	  printf("failed at index %d\n", i);
	  assert(0);
	}
      }
      printf("success (%d, %d)\n", x, y);
      
    }
  }
  
  // cleanup host
  return 0;
}
