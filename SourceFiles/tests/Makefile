FC = mpifort
CC = mpicc

# NetCDF Fortran config
netcdff_libs = $(shell nf-config --flibs)
netcdff_inc  = $(shell nf-config --includedir)

FC_FLAGS_DEBUG = -g -O0
FC_FLAGS = $(FC_FLAGS_DEBUG)

objects = nc_io.o Test_NCF.o

test_nc: $(objects)
	$(FC) $(FC_FLAGS) -I$(netcdff_inc) -o $@ $^ $(netcdff_libs)

%.o: %.F90
	$(FC) $(FC_FLAGS) -I$(netcdff_inc) -c $<

clean:
	rm -f *.o *.mod test_nc

