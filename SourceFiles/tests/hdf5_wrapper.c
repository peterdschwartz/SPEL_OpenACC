#include "H5Tpublic.h"
#include "hdf5.h"
#include <stdlib.h>

/* Open an HDF5 file */
hid_t c_open_file(const char *filename, int mode) {
    hid_t file;
    if (mode == 0)  // Read-Write
        file = H5Fopen(filename, H5F_ACC_RDWR, H5P_DEFAULT);
    else  // Create new file
        file = H5Fcreate(filename, H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);

    return file;
}

/* Close an HDF5 file */
int c_close_file(hid_t file) {
    return (int)H5Fclose(file);
}

/* Write an integer dataset.
 * If ndims == 0, create a scalar dataspace; otherwise, use dims.
 */
int c_write_int(hid_t file, const char *dset_name, 
                const int *data, int ndims, const hsize_t *dims)
{
    hid_t space, dset;
    herr_t status;

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

    return (int)status;
}

/* Write a double dataset.
 * For scalars, ndims should be 0.
 */
int c_write_double(hid_t file, const char *dset_name,
                   const double *data, int ndims, const hsize_t *dims)
{
    hid_t space, dset;
    herr_t status;

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
    return (int)status;
}

int c_read_int(hid_t file, const char *dset_name, int *data) {
    hid_t dset = H5Dopen2(file, dset_name, H5P_DEFAULT);
    if (dset < 0) return -1;

    herr_t status = H5Dread(dset, H5T_NATIVE_INT, H5S_ALL, H5S_ALL, H5P_DEFAULT, data);

    H5Dclose(dset);

    return (int)status;
}

int c_read_dbl(hid_t file_id, const char *dset_name, double *rdata) {
    hid_t dataset;
    herr_t status;

    dataset = H5Dopen2(file_id, dset_name, H5P_DEFAULT);
    if (dataset < 0) return -1;
    status = H5Dread(dataset, H5T_NATIVE_DOUBLE, H5S_ALL, H5S_ALL, H5P_DEFAULT, rdata);
    H5Dclose(dataset);

    return (int)status;
}

/* Similar functions can be created for reading, e.g., c_read_int and c_read_double,
   which call H5Dread instead. */

/* For a scalar, pass ndims = 0. For 1D, 2D, or 3D arrays, pass ndims = 1,2,3 and dims accordingly. */

