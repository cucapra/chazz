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
#define dim 160
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
  /*// Determine where this tile should start in the data array.
  int start_id = tile_id * size;
  // Last tile will handle the remainder.
  if ( tile_id == ( num_tiles - 1 ) ) {
    size = size + ( g_size % num_tiles );
  }*/
  // each tile does the same work for now
  int start_id = 0;

  // Execute vvadd for just this tile's partition. 
  vvadd( &( g_dest[start_id] ), &( g_src0[start_id] ), &( g_src1[start_id] ), size );

  // each tile sends its own bsg_finish and host takes care of it
  bsg_finish();

  bsg_wait_while(1); 
}
