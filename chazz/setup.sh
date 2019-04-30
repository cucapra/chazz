#!/bin/sh

echo 'Loading the FPGA image.'
sudo fpga-load-local-image -S 0 -F -I $AGFI

echo 'Installing manycore libraries.'
sudo -E make -C bsg_bladerunner/bsg_f1_*/cl_manycore/libraries/ install
