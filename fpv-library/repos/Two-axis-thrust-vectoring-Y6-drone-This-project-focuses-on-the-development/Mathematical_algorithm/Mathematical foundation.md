This section explains how the system calculates gimbal servo angles and main motor thrust to produce the desired rotation and
translation of the drone.

First of all, these are simple 3D dynamics equations:

![logo](../Media/simple2eq.png)

F_i is the thrust vector the motor i produces, and r_i is the position vector of the center motor i, being this point where
the vector F_i starts.

If we develop the previous equations:

![logo](../Media/developed6eq.png)

Those six equations form a system of equations of the drone dynamics, but we have to define clearly the unknowns and the 
determined values. The determined values are sent by the remote controller, and are the six expresions at the left side of the six previous equations:

![logo](../Media/6detval.png)

And then we have nine unknowns:

![logo](../Media/9unkn.png)

Those are all the vector components of the three thrust vectors (three motors, three components each).
To manage all this we can create matrices. The matrix A will be the six equations, the matrix x will be the nine unknowns
and the matrix b will be the six determined values. The matrices are the following:

![logo](../Media/3sepmatr.png)

They form this matricial system of equations:

![logo](../Media/matrsysteq.png)

That system is underdetermined, so we have to find the most efficient solution in the 3D solution space. We are looking for 
the minimum-norm solution, the most energy-efficient one. To find it, we resort to the Moore-Penrose pseudoinverse. Its 
formula for a system that has less lines than columns (6x9) is the following:

![logo](../Media/MPpseu.png)

And the minimum-norm solution is:

![logo](../Media/appliedMPpseu.png)

If we calculate A·A^T we get a new 6x6 matrix, which we will call P. Then, we would have to calculate the inverse of P, but
it is a too long procedure thet we can avoid with other mathematical tool: Cholesky factorization. We create a lower 
triangular matrix that satisfies:

![logo](../Media/LLTP.png)

The formula for the diagonal of the L matrix is:

![logo](../Media/Choldiag.png)

And the formula for the lower part of the matrix is:

![logo](../Media/Chollow.png)

That the matrices L and L^T are triangular matrices means that we can solve systems with them easily. The next step is to 
get those systems. This is the procedure:

![logo](../Media/Cholsystprocedure.png)

We have to solve first Ly=b, and this is the formula (being L=l_ij):

![logo](../Media/Lybformula.png)

Now that we have the matrix y, we solve the next system (L^T·u=y) with:

![logo](../Media/LTuyformula.png)

Then, with the matrix u, we can solve x=A^T·u, and we get the minimum-norm solution to Ax=b.
