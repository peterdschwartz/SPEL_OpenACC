module test


contains

   subroutine parent_sub(arg)
      integer :: arg

      call sub1(arg1)

      call sub2(arg2)

   end subroutine parent_sub


   subroutine sub1(arg)
      real, intent(in) :: arg

      real :: A, B, C

      call sub3(A)
      call sub3(B)
      call sub3(C)
   end subroutine sub1

   subroutine sub2(arg)
      real, intent(in) :: arg

      real :: A, B, C

      arg = A*B*C

   end subroutine sub2

   subroutine sub3(arg)
      integer :: arg

      print*, arg

   end subroutine sub3


end module test
