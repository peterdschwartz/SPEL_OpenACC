program nml_test
implicit none
integer :: a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z
if (.true.) then !True 

p = d

else if (.false.) then !False 
STOP 'BRANCH SHOULD BE DEAD 8'

j = e

else !False
STOP 'BRANCH SHOULD BE DEAD 12'

j = w

endif

t = t


print '(A)', 'Done'
end program nml_test 
 
