#include <unistd.h>

#include "bsg_manycore.h"
#include "bsg_set_tile_x_y.h"

/************************************************************************
 Declear an array in DRAM. 
*************************************************************************/

// can specify data in dram here if you want
// maybe can make a .h file with this
//int data[4] __attribute__ ((section (".dram"))) = { -1, 1, 0xF, 0x80000000};
int data[4] __attribute__ ((section (".dram")));
int tileDataRd[4];
int tileDataWr[4];

int main()
{
   int i;
  /************************************************************************
   This will setup the  X/Y coordination. Current pre-defined corrdinations 
   includes:
        __bsg_x         : The X cord inside the group 
        __bsg_y         : The Y cord inside the group
        __bsg_org_x     : The origin X cord of the group
        __bsg_org_y     : The origin Y cord of the group
  *************************************************************************/
  bsg_set_tile_x_y();

  /************************************************************************
   Basic IO outputs bsg_remote_ptr_io_store(IO_X_INDEX, Address, Value)
   Every core will outputs once.
  *************************************************************************/
  bsg_remote_ptr_io_store(IO_X_INDEX,0x1260,__bsg_x);

  /************************************************************************
   Example of Using Prinf. 
   A io mutex was defined for input/output node. 
   The printf will get the mutex first and then output the char stream. 
  *************************************************************************/

  for (int i = 0; i < 4; i++) {
    tileDataWr[i] = tileDataRd[i] + 1; 
  }
   /************************************************************************
    Terminates the Simulation
  *************************************************************************/
    bsg_finish();
  

  bsg_wait_while(1);
}

