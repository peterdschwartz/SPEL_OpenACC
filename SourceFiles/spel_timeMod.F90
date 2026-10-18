module spel_timeMod
  !-----------------------------------------------------------------------
  ! Unit-test stand-ins for the elm_time_manager functions routines call to
  ! test the time step (elm_time_manager needs ESMF's clock). SPEL points
  ! `use elm_time_manager, only : is_first_step, is_first_restart_step` here.
  !
  ! The ELM capture module records get_nstep() and is_first_restart_step()
  ! at every capture; the unit test sets spel_nstep and
  ! spel_first_restart_step from them after reading each step's inputs.
  !-----------------------------------------------------------------------
  implicit none
  private
  integer, public :: spel_nstep = 0
  logical, public :: spel_first_restart_step = .false.
  !$acc declare copyin(spel_nstep, spel_first_restart_step)
  public :: is_first_step, is_first_restart_step

contains

  logical function is_first_step()
    !$acc routine seq
    is_first_step = (spel_nstep == 0)
  end function is_first_step

  logical function is_first_restart_step()
    !$acc routine seq
    is_first_restart_step = spel_first_restart_step
  end function is_first_restart_step

end module spel_timeMod
