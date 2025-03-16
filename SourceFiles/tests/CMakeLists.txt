cmake_minimum_required(VERSION 3.15)

project(test_nc_fortran LANGUAGES Fortran)

# Optional: enable verbose debug output
set(CMAKE_VERBOSE_MAKEFILE ON)

# Optional: enable debug flags
set(CMAKE_Fortran_FLAGS_DEBUG "-g -O0")

# Use find_package to locate NetCDF Fortran
find_package(PkgConfig REQUIRED)
pkg_check_modules(NetCDFF REQUIRED netcdf-fortran)

# Add executable and sources
add_executable(test_nc nc_allocMod.F90 nc_io.F90 Test_NCF.F90)
# Add include directories
include_directories(${NetCDFF_INCLUDE_DIRS})
target_link_directories(test_nc PRIVATE ${NetCDFF_LIBRARY_DIRS})

# Link NetCDF Fortran libraries
target_link_libraries(test_nc PRIVATE ${NetCDFF_LIBRARIES})

# (Optional) Print config summary
message(STATUS "NetCDF Fortran include dirs: ${NetCDFF_INCLUDE_DIRS}")
message(STATUS "NetCDF Fortran libraries: ${NetCDFF_LIBRARIES}")
message(STATUS "NetCDF Fortran lib Dirs: ${NetCDFF_LIBRARY_DIRS}")

