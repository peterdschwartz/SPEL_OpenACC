#include "hdf5.h"
#include <stdlib.h>

/* Write an integer dataset.
 * If ndims == 0, create a scalar dataspace; otherwise, use dims.
 */
int c_write_int(const char *filename, const char *dset_name,
                const int *data, int ndims, const hsize_t *dims)
{
    hid_t file, space, dset;
    herr_t status;

    file = H5Fopen(filename, H5F_ACC_RDWR, H5P_DEFAULT);
    if(file < 0) return -1;

    if(ndims == 0) {
        space = H5Screate(H5S_SCALAR);
    } else {
        space = H5Screate_simple(ndims, dims, NULL);
    }

    dset = H5Dcreate2(file, dset_name, H5T_NATIVE_INT, space,
                      H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    if(dset < 0) return -1;

    status = H5Dwrite(dset, H5T_NATIVE_INT, H5S_ALL, H5S_ALL, H5P_DEFAULT, data);

    H5Dclose(dset);
    H5Sclose(space);
    H5Fclose(file);

    return (int)status;
}

/* Write a double dataset.
 * For scalars, ndims should be 0.
 */
int c_write_double(const char *filename, const char *dset_name,
                   const double *data, int ndims, const hsize_t *dims)
{
    hid_t file, space, dset;
    herr_t status;

    file = H5Fopen(filename, H5F_ACC_RDWR, H5P_DEFAULT);
    if(file < 0) return -1;

    if(ndims == 0) {
        space = H5Screate(H5S_SCALAR);
    } else {
        space = H5Screate_simple(ndims, dims, NULL);
    }

    dset = H5Dcreate2(file, dset_name, H5T_NATIVE_DOUBLE, space,
                      H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
    if(dset < 0) return -1;

    status = H5Dwrite(dset, H5T_NATIVE_DOUBLE, H5S_ALL, H5S_ALL, H5P_DEFAULT, data);

    H5Dclose(dset);
    H5Sclose(space);
    H5Fclose(file);

    return (int)status;
}

/* Similar functions can be created for reading, e.g., c_read_int and c_read_double,
   which call H5Dread instead. */

/* For a scalar, pass ndims = 0. For 1D, 2D, or 3D arrays, pass ndims = 1,2,3 and dims accordingly. */

