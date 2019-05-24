#define _BSD_SOURCE
#define _XOPEN_SOURCE 500

#include <stdio.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <string.h>
#include <time.h>
#include <stdlib.h>

#include <bsg_manycore_driver.h>
#include <bsg_manycore_loader.h>
#include <bsg_manycore_mem.h>
#include <bsg_manycore_errno.h>
#include <bsg_manycore_packet.h>

// this is ahead of current image, but cherry-pick it to curr dir
#include "bsg_manycore_elf.h"

typedef enum transfer_type {
    deviceToHost = 0,
    hostToDevice
} transfer_type_t;

void printReqPkt(hb_mc_request_packet_t *pkt) {
    uint32_t addr = hb_mc_request_packet_get_addr(pkt);
    uint32_t data = hb_mc_request_packet_get_data(pkt);
    uint32_t op_ex = hb_mc_request_packet_get_op_ex(pkt);
    uint32_t x_src = hb_mc_request_packet_get_x_src(pkt);
    uint32_t y_src = hb_mc_request_packet_get_y_src(pkt);
    uint32_t x_dst = hb_mc_request_packet_get_x_dst(pkt);
    uint32_t y_dst = hb_mc_request_packet_get_y_dst(pkt);
    uint32_t op = hb_mc_request_packet_get_op(pkt);
    printf("Manycore request packet: Address 0x%x at coordinates (0x%x, 0x%x) from (0x%x, 0x%x). Operation: 0x%x, Op_ex: 0x%x, Data: 0x%x\n", addr, x_dst, y_dst, x_src, y_src, op, op_ex, data);
}

void printRespPkt(hb_mc_response_packet_t *pkt) {
    uint32_t data = hb_mc_response_packet_get_data(pkt);
    uint32_t load_id = hb_mc_response_packet_get_load_id(pkt);
    uint32_t x_dst = hb_mc_response_packet_get_x_dst(pkt);
    uint32_t y_dst = hb_mc_response_packet_get_y_dst(pkt);
    uint32_t op = hb_mc_response_packet_get_op(pkt);
    printf("Manycore response packet: To coordinates (0x%x, 0x%x). Operation: 0x%x, Load_id: 0x%x, Data: 0x%x\n",  x_dst, y_dst, op, load_id, data);
}

// emulate cudaMemcpy semantics
// userPtr should already be allocated
// on hammerblade virtual and physical addresses are the same (i.e. only physical addresses)
void hammaMemcpy(uint8_t fd, uint32_t x, uint32_t y, uint32_t virtualAddr, void *userPtr, uint32_t numBytes, transfer_type_t transferType) {
    // calculate the number of packets we're going to need. each packets sends 4 bytes
    int numPackets = numBytes / 4;

    if (transferType == deviceToHost) {
		
        hb_mc_response_packet_t *buf = (hb_mc_response_packet_t*)malloc(sizeof(hb_mc_response_packet_t) * numPackets);


        // context, ptr to write to, x, y, virtual address, number of words (how many uint32 / 4 bytes)
        // for some reason need to shift the address by 2 ( / 4. To reflect that fact that it's word addressable not byte addressable!
        int read = hb_mc_copy_from_epa(fd, buf, x, y, virtualAddr >> 2, numPackets);
        
       	if (read == HB_MC_SUCCESS) {
		    // we're going to collect all of the data in a uint32_t buffer and then cast it to void
		    // this should be find b/c every type is <=32-bits.
		    // If over 64 bits this could result in flipping the first and second halves
	
            // store data from the packets in the provided memory
            // the data is in bytes [9,6].
            for (int i = 0; i < numPackets; i++) {
                // printRespPkt(&(buf[i]));

                uint32_t data = hb_mc_response_packet_get_data(&(buf[i]));

                // put the data into the container
                // printf("data: %x\n", data);
                ((uint32_t*)userPtr)[i] = data;
            }
        }
        else {
            printf("read from tile failed %x.\n", virtualAddr);
		    assert(0);
        }		

        // free memory
        free(buf);
    }
    else if (transferType == hostToDevice) {
        uint32_t *data = (uint32_t *) calloc(numPackets, sizeof(uint32_t));

        for (int i = 0; i < numPackets; i++) {
            data[i] = ((uint32_t*)userPtr)[i];
            //printf("sent packet %d: 0x%x\n", i, data[i]);
        }

        // store data in tile
        int write = hb_mc_copy_to_epa(fd, x, y, virtualAddr >> 2, data, numPackets);

        free(data);
        if (write != HB_MC_SUCCESS) {
            printf("writing data to tile (%d, %d)'s DMEM failed.\n", x, y);
            assert(0);
        }
    }
    else {
        assert(0);
    }
} 

// memcpy to/from given symbol name
void hammaSymbolMemcpy(uint8_t fd, uint32_t x, uint32_t y, const char *exeName, const char *symName, void *userPtr, uint32_t numBytes, transfer_type_t transferType) {
    // get the device address of relevant variables
    eva_t addr = 0;
    symbol_to_eva(exeName, symName, &addr);
    printf("Memop with addr: 0x%x\n", addr);

    hammaMemcpy(fd, x, y, addr, userPtr, numBytes, transferType);

}

// loads the kernel for a range of tiles
// the origin of the tile group is assumed to be the first tile in the block
void hammaLoadMultiple(uint8_t fd, char *manycore_program, int x1, int y1, int x2, int y2) {
  int origin_x = x1;
  int origin_y = y1;
  for (uint8_t y = y1; y < y2; y++) {
    for (uint8_t x = x1; x < x2; x++) {
      if (y == 0) {
	printf("trying to load kernel to io core (%d, %d)\n", x, y);
	assert(0);
      }

      // start kernel with origin
      hb_mc_freeze(fd, x, y);
      hb_mc_set_tile_group_origin(fd, x, y, origin_x, origin_y);
      hb_mc_load_binary(fd, manycore_program, &x, &y, 1);
    }
  }
}

void waitForKernel(uint8_t fd, int numTiles) {
    // assuming each tile will send 1 bsg_finish packet, we should wait 
    // until we receive numTiles worth of bsg_finish packets
    for (int i = 0; i < numTiles; i++) {
        hb_mc_request_packet_t manycore_finish;
        hb_mc_read_fifo(fd, 1, (hb_mc_packet_t *) &manycore_finish);
        printReqPkt(&manycore_finish);
    }
}

void hammaRunMultiple(uint8_t fd, int x1, int y1, int x2, int y2) {
  // start all of the tiles
  for (int y = y1; y < y2; y++) {
    for (int x = x1; x < x2; x++) {
      hb_mc_unfreeze(fd, x, y);
    }
  }

  int num_tiles = (x2 - x1) * (y2 - y1);
  
  // recv a packet from each tile marking their completion
  waitForKernel(fd, num_tiles); 

}
