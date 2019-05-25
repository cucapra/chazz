//========================================================================
// Vector Vector Add
//========================================================================
// The code add two vectors using 16 cores and DRAM, Tile 0 intializes the 
// two vectors,then the 16 tiles will exectute the addition in parallel, 
// the last tile will execute the remainder of the Vector and then Tile 0 
// verifies the results and ends the execution.
//
// Author: Shady Agwa, shady.agwa@cornell.edu
// Date: 22 February 2019.

#include "bsg_manycore.h"
#include "bsg_set_tile_x_y.h"

//------------------------------------------------------------------------
// Global data
//------------------------------------------------------------------------

// Define Vectors in SPADs.
#define dim 10
int g_src0[dim]; 
int g_src1[dim];
int g_dest[dim];
// Size Variables & Constants.
const int g_size = dim;
const int size = g_size;

//------------------------------------------------------------------------
// Vector Vecctor Add function
//------------------------------------------------------------------------

void vvadd( int* dest, int* src0, int* src1, int size ) {
  for ( int i = 0; i < size; i++) {
    dest[i] = src0[i] + src1[i];
  }
}

//------------------------------------------------------------------------
// main Function
//------------------------------------------------------------------------

int main()
{
  // Sets the bsg_x and bsg_y global variables.
  bsg_set_tile_x_y();
  int num_tiles = bsg_num_tiles;
  int tile_id   = bsg_x_y_to_id( bsg_x, bsg_y );  
  // each tile does the same work for now
  int start_id = 0;

  // Execute vvadd for just this tile's partition. 
  vvadd( g_dest , g_src0 , g_src1 , size );

  // each tile sends its own bsg_finish and host takes care of it
  bsg_finish();

  bsg_wait_while(1); 
}
