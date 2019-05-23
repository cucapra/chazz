#!/bin/sh
make -C host
make -C device
sudo -E ./host/host ./device/main.riscv
