import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse import hstack
from cuqi.samples import Samples
from cuqi.geometry import Geometry, Continuous1D
import warnings

class Model(object):
    """
    Parameters
    ----------
    forward : 2D ndarray or callable function
        Forward operator
    """
    def __init__(self,forward,range_geometry,domain_geometry):
        """
        Parameters
        ----------
        forward : 2D ndarray or callable function
            Forward operator
        """
        #Check if input is callable
        if callable(forward) is not True:
            raise TypeError("Forward needs to be callable function of some kind")
            
        #Store forward func
        self._forward_func = forward
         
        #Store range_geometry
        if isinstance(range_geometry, int):
            self.range_geometry = Continuous1D(grid=range_geometry)
        elif isinstance(range_geometry, Geometry):
            self.range_geometry = range_geometry
        elif range_geometry is None:
            raise AttributeError("The parameter 'range_geometry' is not specified by the user and it connot be inferred from the attribute 'forward'.")
        else:
            raise TypeError("The parameter 'range_geometry' should be of type 'int' or 'cuqi.geometry.Geometry'.")

        #Store domain_geometry
        if isinstance(domain_geometry, int):
            self.domain_geometry = Continuous1D(grid=domain_geometry)
        elif isinstance(domain_geometry, Geometry):
            self.domain_geometry = domain_geometry
        elif domain_geometry is None:
            raise AttributeError("The parameter 'domain_geometry' is not specified by the user and it connot be inferred from the attribute 'forward'.")
        else:
            raise TypeError("The parameter 'domain_geometry' should be of type 'int' or 'cuqi.geometry.Geometry'.")

    @property
    def domain_dim(self): 
        return self.domain_geometry.dim

    @property
    def range_dim(self): 
        return self.range_geometry.dim
    
               
    def forward(self, x):
        # If input is samples then compute forward for each sample 
        # TODO: Check if this can be done all-at-once for computational speed-up
        if isinstance(x,Samples):
            Ns = x.samples.shape[-1]
            data_samples = np.zeros((self.range_dim,Ns))
            for s in range(Ns):
                data_samples[:,s] = self._forward_func(x.samples[:,s])
            return Samples(data_samples)
        else:
            return self._forward_func(x)

    def __call__(self,x):
        return self.forward(x)

    def gradient(self,x):
        raise NotImplementedError("Gradient is not implemented for this model.")
    
    def __len__(self):
        return self.range_dim
    
class LinearModel(Model):
    """
    Class-based representation of Linear forward operator.

    :param forward: A matrix or callable function representing forward operator.
    :param adjoint: A callable function representing adjoint operator.
    """
    # Linear forward model with forward and adjoint (transpose).
    
    def __init__(self,forward,adjoint=None,range_geometry=None,domain_geometry=None):
        #Assume forward is matrix if not callable (TODO: add more checks)
        if not callable(forward): 
            forward_func = lambda x: self._matrix@x
            adjoint_func = lambda y: self._matrix.T@y
            matrix = forward
        else:
            forward_func = forward
            adjoint_func = adjoint
            matrix = None

        #Check if input is callable
        if callable(adjoint_func) is not True:
            raise TypeError("Adjoint needs to be callable function of some kind")

        #Add adjoint
        self._adjoint_func = adjoint_func

        #Store matrix privately
        self._matrix = matrix

        # Use matrix to derive range_geometry and domain_geometry
        if matrix is not None:
            if range_geometry is None:
                range_geometry = Continuous1D(grid=matrix.shape[0])
            if domain_geometry is None:
                domain_geometry = Continuous1D(grid=matrix.shape[1])  

        #Initialize Model class
        super().__init__(forward_func,range_geometry,domain_geometry)

        if matrix is not None: 
            assert(self.range_dim  == matrix.shape[0]), "The parameter 'forward' dimensions are inconsistent with the parameter 'range_geometry'"
            assert(self.domain_dim == matrix.shape[1]), "The parameter 'forward' dimensions are inconsistent with parameter 'domain_geometry'"

    def adjoint(self,y):
        return self._adjoint_func(y)

    def get_matrix(self):
        if self._matrix is not None: #Matrix exists so return it
            return self._matrix
        else:
            #TODO: Can we compute this faster while still in sparse format?
            mat = csc_matrix((self.range_dim,0)) #Sparse (m x 1 matrix)
            e = np.zeros(self.domain_dim)
            
            # Stacks sparse matricies on csc matrix
            for i in range(self.domain_dim):
                e[i] = 1
                col_vec = self.forward(e)
                mat = hstack((mat,col_vec[:,None])) #mat[:,i] = self.forward(e)
                e[i] = 0

            #Store matrix for future use
            self._matrix = mat

            return self._matrix

    def gradient(self,x):
        return self.adjoint(x)

    def __mul__(self, x):
        return self.forward(x)
    
    def __matmul__(self, x):
        return self*x
        
