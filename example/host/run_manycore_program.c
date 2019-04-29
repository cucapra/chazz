#include "f1_helper.h"

int main (int argc, char *argv[]) {
    assert(argc == 2);
    char *manycore_program = argv[1];
    
    uint8_t fd;
    if (hb_mc_init_host(&fd) != HB_MC_SUCCESS) {
        printf("failed to initialize host.\n");
        return 0;
	}

    // host buffers
    int numBytes = sizeof(int) * 4;
    int *h_a = (int*)malloc(numBytes);
    int *h_b = (int*)malloc(numBytes);

    h_a[0] = 234; h_a[1] = 1; h_a[2] = 25; h_a[3] = 101;

    // the top row (row 0) are io cores so dont send them a program. start at (0,1)
    uint8_t x = 0, y = 1;

    // pause the core
    hb_mc_freeze(fd, 0, 1);

    hb_mc_set_tile_group_origin(fd, 0, 1, 0, 1);

    // load instructions to manycore
    printf("file to be loaded is %s\n", manycore_program);
    // context, binary path, xlist, ylist, numTiles in list
    hb_mc_load_binary(fd, manycore_program, &x, &y, 1);


    // write to core memory
    hammaSymbolMemcpy(fd, x, y, manycore_program, "tileDataRd", (void*)h_a, numBytes, hostToDevice);

    // start the core
    hb_mc_unfreeze(fd, 0,1);

    // wait for completion?
    // timer needed?	
    //usleep(100); /* 100 us */
	
    // wait for the finish (this will be deprecated probably in next version)
    waitForKernel(fd);

    // read back data
    hammaSymbolMemcpy(fd, x, y, manycore_program, "tileDataWr", (void*)h_b, numBytes, deviceToHost); 
    for (int i = 0; i < 4; i++) {
        printf("%d\n", h_b[i]);
    }

    // free host buffers
    free(h_a);
    free(h_b);

    return 0;

}
