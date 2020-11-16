#!/bin/bash
# This script compiles ad flashes the micropython firmware to the pyboard v1.1.
# All the python files located under the software directory will be compiled as frozen bytecode (to save ram) and uploaded to the board toghether with the
# micropython firmware.
# To flash the firmware to the pyboard, it must be in DFU mode, to enter DFU mode, connect DFU pin with 3v3 and push the reset button.
# Requirements:
# 	sudo apt install python-usb python3-usb
#	sudo apt install gcc-arm-none-eabi binutils-arm-none-eabi openocd
#   sudo apt install dfu-util

board="PYBV11"
source="$PWD/software/firmware"
dest="$PWD/micropython"
modules="/modules"
mpy="/mpy-cross"
port="/ports/stm32"
manifest="/boards/manifest.py"

# Enables _thread module in ports/stm32/mpconfigport.h
sed -i "s|#define MICROPY_PY_THREAD           (0)|#define MICROPY_PY_THREAD           (1)|g" $dest$port/mpconfigport.h

rm -rv $dest$modules/*

for dir in $(find $source -type d); do
	cd $dir
	#for file in $(find -maxdepth 1 -type f -name "*.p"); do  # uncomment if file extension p
	for file in $(find -maxdepth 1 -type f -name "*.py"); do
		basename=$(basename $file)
		dirname=$(echo $(pwd) | sed "s|"$source"||g")
		mkdir -p $dest$modules$dirname
		cp -fv $(pwd)/$basename $dest$modules$dirname/$basename
		#mv -v $dest$modules$dirname/$basename $dest$modules$dirname/$(basename $basename .p).py  # uncomment if file extension p
		done
	done
cd $dest
rm -v $dest$port$manifest
for dir in $(find $dest$modules -type d); do
	cd $dir
	for file in $(find -maxdepth 1 -type f -name "*.py"); do
		echo freeze\(\"\$\(MPY_DIR\)\/$(basename $modules)\", \"$(echo $dir/$(basename $file) | sed "s|"$dest$modules/"||g")\"\) >> $dest$port$manifest
		done
	done
cd $dest$mpy
make
cd $dest$port
make submodules
make BOARD=$board clean
make BOARD=$board
make BOARD=$board deploy
