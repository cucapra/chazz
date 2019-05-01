#!/bin/sh

cd ./host
make

cd ../device
make

cd ..
sudo -E ./host/host ./device/main.riscv
