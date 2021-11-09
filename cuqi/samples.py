import numpy as np
import matplotlib.pyplot as plt
from cuqi.diagnostics import Geweke
from cuqi.geometry import _DefaultGeometry
from copy import copy

class CUQIarray(np.ndarray):

    def __repr__(self) -> str: 
        return "CUQIarray: NumPy array wrapped with geometry.\n" + \
               "---------------------------------------------\n\n" + \
            "Geometry:\n {}\n\n".format(self.geometry) + \
            "Parameters:\n {}\n\n".format(self.is_par) + \
            "Array:\n" + \
            super().__repr__()

    def __new__(cls, input_array, is_par=True, geometry=None):
        # Input array is an already formed ndarray instance
        # We first cast to be our class type
        obj = np.asarray(input_array).view(cls)
        # add the new attribute to the created instance
        obj.is_par = is_par
        obj.geometry = geometry
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        # see InfoArray.__array_finalize__ for comments
        if obj is None: return
        self.is_par = getattr(obj, 'is_par', True)
        self.geometry = getattr(obj, 'geometry', None)

    @property
    def funvals(self):
        if self.is_par is True:
            vals = self.geometry.par2fun(self)
        else:
            vals = self

        return CUQIarray(vals,is_par=False,geometry=self.geometry) #vals.view(np.ndarray)   

    @property
    def parameters(self):
        if self.is_par is False:
            vals = self.geometry.fun2par(self)
        else:
            vals = self

        return CUQIarray(vals,is_par=True,geometry=self.geometry)
    
    def plot(self, **kwargs):
        self.geometry.plot(self.funvals, is_par=False, **kwargs)


class Data(object):
    """
    An container type object to represent data objects equipped with geometry.
    """

    def __init__(self, parameters=None, geometry=None, funvals=None):
        
        # Allow setting either parameter or function values, but not both.
        # If both provided, function values take precedence (to be confirmed).
        if parameters is not None and funvals is not None:
            parameters = None
        
        if parameters is not None:
            self.parameters = parameters
        
        if funvals is not None:
            self.funvals = funvals

        self.geometry = geometry
        
    def plot(self, **kwargs):
        self.geometry.plot(self.funvals, is_par=False, **kwargs)
    
    @property
    def parameters(self):
        return self._parameters
    
    @parameters.setter
    def parameters(self, value):
        self._parameters = value
        self.has_parameters = True
        self.has_funvals = False
    
    @property
    def funvals(self):
        if self.has_funvals:
            return self._funvals
        else:
            return self.geometry.par2fun(self.parameters)
    
    @funvals.setter
    def funvals(self, value):
        self.has_funvals = True
        self.has_parameters = False
        self._funvals = value


class Samples(object):
    """
    An object used to store samples from distributions. 

    Parameters
    ----------
    samples : ndarray
        Contains the raw samples as a numpy array indexed by the last axis of the array.

    geometry : cuqi.geometry.Geometry, default None
        Contains the geometry related of the samples

    Attributes
    ----------
    shape : tuple
        Returns the shape of samples.

    Methods
    ----------
    :meth:`plot`: Plots one or more samples.
    :meth:`plot_ci`: Plots a confidence interval for the samples.
    :meth:`plot_mean`: Plots the mean of the samples.
    :meth:`plot_std`: Plots the std of the samples.
    :meth:`plot_chain`: Plots all samples of one or more variables (MCMC chain).
    :meth:`burnthin`: Removes burn-in and thins samples.
    :meth:`diagnostics`: Conducts diagnostics on the chain.
    """
    def __init__(self, samples, geometry=None):
        self.samples = samples
        self.geometry = geometry

    @property
    def shape(self):
        return self.samples.shape

    @property
    def geometry(self):
        if self._geometry is None:
            self._geometry = _DefaultGeometry(grid=np.prod(self.samples.shape[:-1]))
        return self._geometry

    @geometry.setter
    def geometry(self,inGeometry):
        self._geometry = inGeometry

    def burnthin(self, Nb, Nt=1):
        """
        Remove burn-in and thin samples. 
        The burnthinned samples are returned as a new Samples object.
        
        Parameters
        ----------
        Nb : int
            Number of samples to remove as burn-in from the start of the chain.
        
        Nt : int
            Thin samples by selecting every Nt sample in the chain (after burn-in)

        Example
        ----------
        # Remove 100 samples burn in and select every 2nd sample after burn-in
        # Store as new samples object
        S_burnthin = S.burnthin(100,2) 

        # Same thing as above, but replace existing samples object
        # (the burn-in and thinned samples are lost)
        S = S.burnthin(100,2) 
        """
        new_samples = copy(self)
        new_samples.samples = self.samples[...,Nb::Nt]
        return new_samples

    def plot_mean(self,*args,**kwargs):
        # Compute mean assuming samples are index in last dimension of nparray
        mean = np.mean(self.samples,axis=-1)

        # Plot mean according to geometry
        return self.geometry.plot(mean,*args,**kwargs)

    def plot_std(self,*args,**kwargs):
        # Compute std assuming samples are index in last dimension of nparray
        std = np.std(self.samples,axis=-1)

        # Plot mean according to geometry
        return self.geometry.plot(std,*args,**kwargs)

    def plot(self,sample_indices=None,*args,**kwargs):
        Ns = self.samples.shape[-1]
        if sample_indices is None:
            if Ns < 10:
                return self.geometry.plot(self.samples,*args,**kwargs)
            else:
                print("Plotting 5 randomly selected samples")
                return self.geometry.plot(self.samples[:,np.random.choice(Ns,5,replace=False)],*args,**kwargs)
        else:
            return self.geometry.plot(self.samples[:,sample_indices],*args,**kwargs)

    def plot_chain(self,variable_indices,*args,**kwargs):
        if 'label' in kwargs.keys():
            raise Exception("Argument 'label' cannot be passed by the user")
        if hasattr(self.geometry,"variables"):
            variables = np.array(self.geometry.variables) #Convert to np array for better slicing
            variables = np.array(variables[variable_indices]).flatten()
        else:
            variables = np.array(variable_indices).flatten()
        lines = plt.plot(self.samples[variable_indices,:].T,*args,**kwargs)
        plt.legend(variables)
        return lines

    def plot_ci(self,percent,exact=None,*args,plot_envelope_kwargs={},**kwargs):
        """
        Plots the confidence interval for the samples according to the geometry.

        Parameters
        ---------
        percent : int
            The percent confidence to plot (i.e. 95, 99 etc.)
        
        exact : ndarray, default None
            The exact value (for comparison)

        plot_envelope_kwargs : dict, default {}
            Keyword arguments for the plot_envelope method
        
        """
        
        # Compute statistics
        mean = np.mean(self.samples,axis=-1)
        lb = (100-percent)/2
        up = 100-lb
        lo_conf, up_conf = np.percentile(self.samples, [lb, up], axis=-1)

        #Extract plotting keywords and put into plot_envelope
        if len(plot_envelope_kwargs)==0:
            pe_kwargs={}
        else:
            pe_kwargs = plot_envelope_kwargs
        if "is_par"   in kwargs.keys(): pe_kwargs["is_par"]  =kwargs.get("is_par")
        if "plot_par" in kwargs.keys(): pe_kwargs["plot_par"]=kwargs.get("plot_par")   

        lci = self.geometry.plot_envelope(lo_conf, up_conf,color='dodgerblue',**pe_kwargs)

        lmn = self.geometry.plot(mean,*args,**kwargs)
        if exact is not None: #TODO: Allow exact to be defined in different space than mean?
            lex = self.geometry.plot(exact,*args,**kwargs)
            plt.legend([lmn[0], lex[0], lci],["Mean","Exact","Confidence Interval"])
        else:
            plt.legend([lmn[0], lci],["Mean","Confidence Interval"])

    def diagnostics(self):
        # Geweke test
        Geweke(self.samples.T)
