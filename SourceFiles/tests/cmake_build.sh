#!/bin/bash

if [ -d build ]; then
	rm -rf build
fi

mkdir -p build && cd build

cmake .. \
	-DCMAKE_Fortran_COMPILER=mpifort \
	-DCMAKE_C_COMPILER=mpicc \
	-DCMAKE_BULD_TYPE=Debug

make

