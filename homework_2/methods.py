import numpy as np
import scipy
import time
from collections import defaultdict
from scipy.optimize.linesearch import scalar_search_wolfe2


class LineSearchTool(object):
    """
    Line search tool for adaptively tuning the step size of the algorithm.

    method : String containing 'Wolfe', 'Armijo' or 'Constant'
        Method of tuning step-size.
        Must be be one of the following strings:
            - 'Wolfe' -- enforce strong Wolfe conditions;
            - 'Armijo" -- adaptive Armijo rule;
            - 'Constant' -- constant step size.
    kwargs :
        Additional parameters of line_search method:

        If method == 'Wolfe':
            c1, c2 : Constants for strong Wolfe conditions
        If method == 'Armijo':
            c1 : Constant for Armijo rule
            alpha_0 : Starting point for the backtracking procedure.
        If method == 'Constant':
            c : The step size which is returned on every step.
    """

    def __init__(self, method='Wolfe', **kwargs):
        self._method = method
        if self._method == 'Wolfe':
            self.c1 = kwargs.get('c1', 1e-4)
            self.c2 = kwargs.get('c2', 0.9)
        elif self._method == 'Armijo':
            self.c1 = kwargs.get('c1', 1e-4)
            self.alpha_0 = kwargs.get('alpha_0', 1.0)
        elif self._method == 'Constant':
            self.c = kwargs.get('c', 1.0)
        else:
            raise ValueError('Unknown method {}'.format(method))

    @classmethod
    def from_dict(cls, options):
        if type(options) != dict:
            raise TypeError('LineSearchTool initializer must be of type dict')
        return cls(**options)

    def to_dict(self):
        return self.__dict__

    def line_search(self, oracle, x_k, d_k, previous_alpha=None):
        """
        Finds the step size alpha for a given starting point x_k
        and for a given search direction d_k that satisfies necessary
        conditions for phi(alpha) = oracle.func(x_k + alpha * d_k).

        Parameters
        ----------
        oracle : BaseSmoothOracle-descendant object
            Oracle with .func_directional() and .grad_directional() methods implemented for computing
            function values and its directional derivatives.
        x_k : np.array
            Starting point
        d_k : np.array
            Search direction
        previous_alpha : float or None
            Starting point to use instead of self.alpha_0 to keep the progress from
             previous steps. If None, self.alpha_0, is used as a starting point.

        Returns
        -------
        alpha : float or None if failure
            Chosen step size
        """
        phi = lambda alpha: oracle.func_directional(x_k, d_k, alpha)
        derphi = lambda alpha: oracle.grad_directional(x_k, d_k, alpha)

        def backtracking(phi, derphi, c1, alpha0=1):
            alpha = alpha0
            while phi(alpha) > phi(0) + c1 * alpha * derphi(0):
                alpha /= 2
            return alpha

        if self._method == 'Constant':
            return self.c
        elif self._method == 'Armijo':
            previous_alpha = previous_alpha or self.alpha_0
            return backtracking(phi, derphi, self.c1, previous_alpha)
        elif self._method == 'Wolfe':
            best_alpha = scalar_search_wolfe2(phi, derphi, c1=self.c1, c2=self.c2)[0]
            return best_alpha if best_alpha is not None else backtracking(phi=phi, derphi=derphi, c1=self.c1)


def get_line_search_tool(line_search_options=None):
    if line_search_options:
        if type(line_search_options) is LineSearchTool:
            return line_search_options
        else:
            return LineSearchTool.from_dict(line_search_options)
    else:
        return LineSearchTool()


class GradientDescent(object):
    """
    Gradient descent optimization algorithm.

    oracle : BaseSmoothOracle-descendant object
        Oracle with .func() and .grad() methods implemented for computing
        function value and its gradient respectively.
    x_0 : np.array
        Starting point for optimization algorithm
    tolerance : float
        Epsilon value for stopping criterion.
    line_search_options : dict, LineSearchTool or None
        Dictionary with line search options. See LineSearchTool class for details.
    """

    def __init__(self, oracle, x_0, tolerance=1e-10, line_search_options=None):
        self.oracle = oracle
        self.x_0 = x_0.copy()
        self.tolerance = tolerance
        self.line_search_tool = get_line_search_tool(line_search_options)
        self.hist = defaultdict(list)
        self.hist["time"] = []
        self.hist["func"] = []
        self.hist["grad_norm"] = []
        self.hist["x"] = []
        # self.hist["x_star"] = []

    def run(self, max_iter=100):
        """
        Runs gradient descent for max_iter iterations or until stopping
        criteria is satisfied, starting from point x_0. Saves function values
        and time in self.hist

        self.hist : dictionary of lists
        Dictionary containing the progress information
        Dictionary has to be organized as follows:
            - self.hist['time'] : list of floats, containing time in seconds passed from the start of the method
            - self.hist['func'] : list of function values f(x_k) on every step of the algorithm
            - self.hist['grad_norm'] : list of values Euclidian norms ||g(x_k)|| of the gradient on every step of the algorithm
            - self.hist['x'] : list of np.arrays, containing the trajectory of the algorithm. ONLY STORE IF x.size <= 2
            - self.hist['x_star']: np.array containing x at last iteration
        """
        start_time = time.time()
        grad_x_0 = self.oracle.grad(self.x_0)
        grad_x_0_norm = grad_x_0.dot(grad_x_0)
        x_k = self.x_0.copy()

        for k in range(max_iter + 1):
            self.hist["time"].append(time.time() - start_time)
            self.hist["func"].append(self.oracle.func(x_k))
            grad_x_k = self.oracle.grad(x_k)
            self.hist["grad_norm"].append(np.sqrt(grad_x_k.dot(grad_x_k)))

            if grad_x_k.dot(grad_x_k) <= grad_x_0_norm * self.tolerance:
                break

            alpha = self.line_search_tool.line_search(self.oracle, x_k, -grad_x_k)

            if grad_x_k.size <= 2:
                self.hist["x"].append(-alpha * grad_x_k)

            x_k = x_k - alpha * grad_x_k

        self.hist["x_star"] = x_k
