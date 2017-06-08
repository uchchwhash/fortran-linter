c       example legacy code
        program ancient
        real x
        integer i, j

        x = 5.0
        if (x .eq. 5) print *, 'all is well'
10      if (x .eq. 6) then ! useless label

            do i=1,18
20          print *, 'something impossible just happened'
            goto 20
          end do ! let's do the indentation wrong
        end if
        end

        function square(x)
        real x
        square = x * x

        x = y ! but what is y?
            
c       some lines left blank for no apparent reason
        end function

        subroutine throwaway(unused)
        end subroutine
