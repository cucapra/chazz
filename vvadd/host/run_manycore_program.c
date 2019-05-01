#include "f1_helper.h"

typedef struct Vector2Int {
    int x;
    int y;
} Vector2Int;

void init_vec2(Vector2Int *v, int x, int y) {
    v->x = x;
    v->y = y;
}

// todo put in f1_helper
void hammaLoadMultiple(uint8_t fd, char *manycore_program, Vector2Int **tile_coords, int num_tiles) {
    // take the first tile in the group as the group origin
    // you need to call set origin to "prepare" the manycore for where to send the kernel???
    int origin_x = tile_coords[0]->x;
    int origin_y = tile_coords[0]->y;

    for (int i = 0; i < num_tiles; i++) {
        Vector2Int *coord = tile_coords[i];
        uint8_t x = coord->x;
        uint8_t y = coord->y;
        printf("loading kernel for (%d, %d)\n", x, y);
        
        if (y == 0) {
            printf("trying to load kernel to io core (%d, %d)\n", x, y);
            assert(0);
        }

        hb_mc_freeze(fd, x, y);
        hb_mc_set_tile_group_origin(fd, x, y, origin_x, origin_y);
        hb_mc_load_binary(fd, manycore_program, &x, &y, 1);   
        
    }
}

void hammaRunMultiple(uint8_t fd, Vector2Int **tile_coords, int num_tiles) {
    // start all of the tiles
    for (int i = 0; i < num_tiles; i++) {
        Vector2Int *coord = tile_coords[i];
        int x = coord->x;
        int y = coord->y;
        hb_mc_unfreeze(fd, x, y);
        printf("start tile (%d, %d)\n", x, y);
    }
 
    // recv a packet from each tile marking their completion
    waitForKernel(fd, num_tiles); 

}

// 4 x 4 - 4 ( the t p row, in charge of io ) 
#define NUM_TILES 12

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
   
    // generate a list of tiles to run on
    Vector2Int *tile_coords[NUM_TILES];
    for (int i = 0; i < NUM_TILES; i++) {
        Vector2Int *tile = (Vector2Int*)malloc(sizeof(Vector2Int));
        int x = i % 4;
        int y = 1 + (i / 4);
        init_vec2(tile, x, y);
        tile_coords[i] = tile; 
    }
 
    hammaLoadMultiple(fd, manycore_program, tile_coords, NUM_TILES);
    uint8_t x = 0, y = 1;
/*
    hb_mc_set_tile_group_origin(fd, 0, 1, 0, 1);
    hb_mc_freeze(fd, 0, 1);
    hb_mc_load_binary(fd, manycore_program, &x, &y, 1);
*/

    // do a data copy of the whole array to tile spads
    // NOTE -- must be done after loading the kernel to hammerblade
    for (int i = 0; i < NUM_TILES; i++) {
        int x = tile_coords[i]->x;
        int y = tile_coords[i]->y;
        printf("memcpy %d %d\n", x, y);
        hammaSymbolMemcpy(fd, x, y, manycore_program, "g_src1", (void*)h_src1, dim * sizeof(int), hostToDevice);
        hammaSymbolMemcpy(fd, x, y, manycore_program, "g_src0", (void*)h_src0, dim * sizeof(int), hostToDevice);
    }

    //hammaSymbolMemcpy(fd, x, y, manycore_program, "g_src1", (void*)h_src1, dim * sizeof(int), hostToDevice);
    //hammaSymbolMemcpy(fd, x, y, manycore_program, "g_src0", (void*)h_src0, dim * sizeof(int), hostToDevice);  
//empty dmaps list
	
    hammaRunMultiple(fd, tile_coords, NUM_TILES);
    /*hb_mc_unfreeze(fd, 0, 1);
    hb_mc_request_packet_t manycore_finish;
    hb_mc_read_fifo(fd, 1, (hb_mc_packet_t *) &manycore_finish);
    printReqPkt(&manycore_finish); 
*/
    // TEMP -- everytile adds the whole array and we're just copying and check each the same
    int *h_dest = (int*)malloc(dim * sizeof(int));

    for (int i = 0; i < NUM_TILES; i++) {
	    int x = tile_coords[i]->x;
        int y = tile_coords[i]->y;
	    hammaSymbolMemcpy(fd, x, y, manycore_program, "g_dest", (void*)h_dest, dim * sizeof(int), deviceToHost);

        for (int i = 0; i < dim; i++) {
            //printf("2 * %d ?= %d\n", i, h_dest[i]);
            if (h_dest[i] != 2 * i) {
                printf("failed at index %d\n", i);
                assert(0);
            }
        }
        printf("success (%d, %d)\n", x, y);

    }
	// cleanup host
	return 0;
}
