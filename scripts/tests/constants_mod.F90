module constants_mod

  integer, parameter :: i_const = 5
  integer, parameter :: nlevdecomp_full = 10
  real :: param1(1:nlevdecomp_full)
  real, allocatable :: param2(:)
  real, allocatable :: notused(:)

  logical :: use_fates = .true.
  contains

  subroutine init_params()
    allocate(     notused    (1:i_const), param2      (1:i_const))
  end subroutine init_params

end module constants_mod
