#!/bin/sh

# Load the FPGA image.
sudo fpga-load-local-image -S 0 -F -I $AGFI
