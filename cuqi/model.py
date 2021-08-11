import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse import hstack
from cuqi.samples import Samples
from cuqi.geometry import Continuous1D
import warnings

class Model(object):
    """
    Parameters
    ----------
    forward : 2D ndarray or callable function
        Forward operator
    """
    def __init__(self,forward,dim=None,rangeGeom=None,domainGeom=None):
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
        
        #Store range and domain geometry objects
        self._dim = dim
        self.rangeGeom = rangeGeom
        self.domainGeom = domainGeom

    @property
    def dim(self): #dim is derived from rangeGeom and domainGeom objects
        dim_old = self._dim 
        if self.rangeGeom is not None and self.domainGeom is not None: 
            self._dim = (len(self.rangeGeom.grid), len(self.domainGeom.grid)) #TODO: change len(self.domainGeom.grid) to self.domainGeom.ndofs
        if dim_old is not None and self._dim != dim_old:
            warnings.warn("'Model.dim' value was changed to be compatible with 'rangeGeom' and 'domainGeom' ")
        return self._dim

    @property
    def rangeGeom(self):
        if self._rangeGeom is None:
            if self._dim is not None:
                self._rangeGeom = Continuous1D(dim=[self._dim[0]])
        return self._rangeGeom
    
    @rangeGeom.setter
    def rangeGeom(self,inRangeGeom):
        self._rangeGeom = inRangeGeom

    @property
    def domainGeom(self):
        if self._domainGeom is None:
            if self._dim is not None:
                self._domainGeom = Continuous1D(dim=[self._dim[1]])
        return self._domainGeom
    
    @domainGeom.setter
    def domainGeom(self,inDomainGeom):
        self._domainGeom = inDomainGeom
               
    def forward(self, x):
        # If input is samples then compute forward for each sample 
        # TODO: Check if this can be done all-at-once for computational speed-up
        if isinstance(x,Samples):
            Ns = x.samples.shape[-1]
            data_samples = np.zeros((self.dim[0],Ns))
            for s in range(Ns):
                data_samples[:,s] = self._forward_func(x.samples[:,s])
            return Samples(data_samples)
        else:
            return self._forward_func(x)
    
class LinearModel(Model):
    """
    Class-based representation of Linear forward operator.

    :param forward: A matrix or callable function representing forward operator.
    :param adjoint: A callable function representing adjoint operator.
    :param dim: Dimensions of linear model.
    """
    # Linear forward model with forward and adjoint (transpose).
    
    def __init__(self,forward,adjoint=None,dim=None,rangeGeom=None,domainGeom=None):
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

        #Initialize Model class
        super().__init__(forward_func,dim=dim,rangeGeom=rangeGeom,domainGeom=domainGeom) 

    @property
    def rangeGeom(self):
        if super().rangeGeom is None:    
            if  hasattr(self._matrix, 'shape'):
                self._rangeGeom = Continuous1D(dim=[self._matrix.shape[0]]) #TODO: change Geometry.dim to Geometry.ndofs
        return self._rangeGeom

    @rangeGeom.setter
    def rangeGeom(self,inRangeGeom):
        super(LinearModel, type(self)).rangeGeom.fset(self, inRangeGeom)

    @property
    def domainGeom(self):
        if super().domainGeom is None:  
            if hasattr(self._matrix, 'shape'):
                self._domainGeom = Continuous1D(dim=[self._matrix.shape[1]]) #TODO: change Geometry.dim to Geometry.ndofs
        return self._domainGeom

    @domainGeom.setter
    def domainGeom(self,inDomainGeom):
        super(LinearModel, type(self)).domainGeom.fset(self, inDomainGeom)

    def adjoint(self,y):
        return self._adjoint_func(y)

    def get_matrix(self):
        if self._matrix is not None: #Matrix exists so return it
            return self._matrix
        else:
            #TODO: Can we compute this faster while still in sparse format?
            mat = csc_matrix((self.dim[0],0)) #Sparse (m x 1 matrix)
            e = np.zeros(self.dim[1])
            
            # Stacks sparse matricies on csc matrix
            for i in range(self.dim[1]):
                e[i] = 1
                col_vec = self.forward(e)
                mat = hstack((mat,col_vec[:,None])) #mat[:,i] = self.forward(e)
                e[i] = 0

            #Store matrix for future use
            self._matrix = mat

            return self._matrix

    def __mul__(self, x):
        return self.forward(x)
    
    def __matmul__(self, x):
        return self*x

        
