from abc import ABC, abstractmethod
import os
import numpy as np
import pickle as pkl
import warnings
import cuqi
from cuqi.samples import Samples

try:
    from progressbar import progressbar
except ImportError:
    def progressbar(iterable, **kwargs):
        warnings.warn("Module mcmc: Progressbar not found. Install progressbar2 to get sampling progress.")
        return iterable

class SamplerNew(ABC):
    """ Abstract base class for all samplers.
    
    Provides a common interface for all samplers. The interface includes methods for sampling, warmup and getting the samples in an object oriented way.

    Samples are stored in a list to allow for dynamic growth of the sample set. Returning samples is done by creating a new Samples object from the list of samples.

    """
    _STATE_KEYS = {'current_point'}
    """ Set of keys for the state dictionary. """

    _HISTORY_KEYS = {'_samples', '_acc'}
    """ Set of keys for the history dictionary. """

    def __init__(self, target: cuqi.density.Density, initial_point=None, callback=None):
        """ Initializer for abstract base class for all samplers.
        
        Parameters
        ----------
        target : cuqi.density.Density
            The target density.

        initial_point : array-like, optional
            The initial point for the sampler. If not given, the sampler will choose an initial point.

        callback : callable, optional
            A function that will be called after each sample is drawn. The function should take two arguments: the sample and the index of the sample.
            The sample is a 1D numpy array and the index is an integer. The callback function is useful for monitoring the sampler during sampling.

        """

        self.target = target
        self.initial_point = initial_point
        self.current_point = initial_point
        self.callback = callback
        self._is_initialized = False

    def initialize(self):
        """ Delayed initialization of the sampler. To happen after target is set """

        if self._is_initialized:
            raise ValueError("Sampler is already initialized.")
        
        if self.target is None:
            raise ValueError("Cannot initialize sampler without a target density.")
               
        self._set_defaults()

        self._initialize_state()

        self._initialize_history()

        self._validate_initialization()

        self._is_initialized = True

    # ------------ Abstract methods to be implemented by subclasses ------------
    @abstractmethod
    def step(self):
        """ Perform one step of the sampler by transitioning the current point to a new point according to the sampler's transition kernel. """
        pass

    @abstractmethod
    def tune(self):
        """ Tune the parameters of the sampler. This method is called after each step of the warmup phase. """
        pass

    @abstractmethod
    def validate_target(self):
        """ Validate the target is compatible with the sampler. Called when the target is set. Should raise an error if the target is not compatible. """
        pass

    # -- _pre_sample and _pre_warmup methods: can be overridden by subclasses --
    def _pre_sample(self):
        """ Any code that needs to be run before sampling. """
        pass

    def _pre_warmup(self):
        """ Any code that needs to be run before warmup. """
        pass

    # ------------ Public attributes ------------
    @property
    def dim(self):
        """ Dimension of the target density. """
        return self.target.dim

    @property
    def geometry(self):
        """ Geometry of the target density. """
        return self.target.geometry
    
    @property
    def target(self) -> cuqi.density.Density:
        """ Return the target density. """
        return self._target
    
    @target.setter
    def target(self, value):
        """ Set the target density. Runs validation of the target. """
        self._target = value
        if self._target is not None:
            self.validate_target()
            self.initialize()

    # ------------ Public methods ------------

    def get_samples(self) -> Samples:
        """ Return the samples. The internal data-structure for the samples is a dynamic list so this creates a copy. """
        return Samples(np.array(self._samples).T, self.target.geometry)
    
    def reset(self):
        """ Reset sampler state and history. """

        # Loop over state and reset to None
        for key in self._STATE_KEYS:
            setattr(self, key, None)

        # Loop over history and reset to None
        for key in self._HISTORY_KEYS:
            setattr(self, key, None)

        self.initialize()
    
    def save_checkpoint(self, path):
        """ Save the state of the sampler to a file. """

        state = self.get_state()

        # Convert all CUQIarrays to numpy arrays since CUQIarrays do not get pickled correctly
        for key, value in state['state'].items():
            if isinstance(value, cuqi.array.CUQIarray):
                state['state'][key] = value.to_numpy()

        with open(path, 'wb') as handle:
            pkl.dump(state, handle, protocol=pkl.HIGHEST_PROTOCOL)

    def load_checkpoint(self, path):
        """ Load the state of the sampler from a file. """

        with open(path, 'rb') as handle:
            state = pkl.load(handle)

        self.set_state(state)

    def sample(self, Ns, batch_size=0, sample_path='./CUQI_samples/') -> 'SamplerNew':
        """ Sample Ns samples from the target density.

        Parameters
        ----------
        Ns : int
            The number of samples to draw.

        batch_size : int, optional
            The batch size for saving samples to disk. If 0, no batching is used. If positive, samples are saved to disk in batches of the specified size.

        sample_path : str, optional
            The path to save the samples. If not specified, the samples are saved to the current working directory under a folder called 'CUQI_samples'.

        """

        # Initialize batch handler
        if batch_size > 0:
            batch_handler = _BatchHandler(batch_size, sample_path)

        # Any code that needs to be run before sampling
        self._pre_sample()

        # Draw samples
        for _ in progressbar( range(Ns) ):
            
            # Perform one step of the sampler
            acc = self.step()

            # Store samples
            self._acc.append(acc)
            self._samples.append(self.current_point)

            # Add sample to batch
            if batch_size > 0:
                batch_handler.add_sample(self.current_point)

            # Call callback function if specified            
            self._call_callback(self.current_point, len(self._samples)-1)
                
        return self
    

    def warmup(self, Nb, tune_freq=0.1) -> 'SamplerNew':
        """ Warmup the sampler by drawing Nb samples.

        Parameters
        ----------
        Nb : int
            The number of samples to draw during warmup.

        tune_freq : float, optional
            The frequency of tuning. Tuning is performed every tune_freq*Nb samples.

        """

        tune_interval = max(int(tune_freq * Nb), 1)

        # Any code that needs to be run before warmup
        self._pre_warmup()

        # Draw warmup samples with tuning
        for idx in progressbar(range(Nb)):

            # Perform one step of the sampler
            acc = self.step()

            # Tune the sampler at tuning intervals
            if (idx + 1) % tune_interval == 0:
                self.tune(tune_interval, idx // tune_interval) 

            # Store samples
            self._acc.append(acc)
            self._samples.append(self.current_point)

            # Call callback function if specified
            self._call_callback(self.current_point, len(self._samples)-1)

        return self
    
    def get_state(self) -> dict:
        """ Return the state of the sampler. 

        The state is used when checkpointing the sampler.

        The state of the sampler is a dictionary with keys 'metadata' and 'state'.
        The 'metadata' key contains information about the sampler type.
        The 'state' key contains the state of the sampler.

        For example, the state of a "MH" sampler could be:

        state = {
            'metadata': {
                'sampler_type': 'MH'
            },
            'state': {
                'current_point': np.array([...]),
                'current_target_logd': -123.45,
                'scale': 1.0,
                ...
            }
        }
        """   
        state = {
            'metadata': {
                'sampler_type': self.__class__.__name__
            },
            'state': {
                key: getattr(self, key) for key in self._STATE_KEYS
            }
        }
        return state

    def set_state(self, state: dict):
        """ Set the state of the sampler.

        The state is used when loading the sampler from a checkpoint.

        The state of the sampler is a dictionary with keys 'metadata' and 'state'.

        For example, the state of a "MH" sampler could be:

        state = {
            'metadata': {
                'sampler_type': 'MH'
            },
            'state': {
                'current_point': np.array([...]),
                'current_target_logd': -123.45,
                'scale': 1.0,
                ...
            }
        }
        """
        if state['metadata']['sampler_type'] != self.__class__.__name__:
            raise ValueError(f"Sampler type in state dictionary ({state['metadata']['sampler_type']}) does not match the type of the sampler ({self.__class__.__name__}).")
        
        for key, value in state['state'].items():
            if key in self._STATE_KEYS:
                setattr(self, key, value)
            else:
                raise ValueError(f"Key {key} not recognized in state dictionary of sampler {self.__class__.__name__}.")
            
    def get_history(self) -> dict:
        """ Return the history of the sampler. """
        history = {
            'metadata': {
                'sampler_type': self.__class__.__name__
            },
            'history': {
                key: getattr(self, key) for key in self._HISTORY_KEYS
            }
        }
        return history
    
    def set_history(self, history: dict):
        """ Set the history of the sampler. """
        if history['metadata']['sampler_type'] != self.__class__.__name__:
            raise ValueError(f"Sampler type in history dictionary ({history['metadata']['sampler_type']}) does not match the type of the sampler ({self.__class__.__name__}).")
        
        for key, value in history['history'].items():
            if key in self._HISTORY_KEYS:
                setattr(self, key, value)
            else:
                raise ValueError(f"Key {key} not recognized in history dictionary of sampler {self.__class__.__name__}.")

    # ------------ Private methods ------------

    def _call_callback(self, sample, sample_index):
        """ Calls the callback function. Assumes input is sample and sample index"""
        if self.callback is not None:
            self.callback(sample, sample_index)

    def _set_defaults(self):
        """ Set the default initial point for the sampler. """
        if self.target is None:
            raise ValueError("Cannot get default initial point without a target density.")
        self.initial_point = self._default_initial_point
        self.current_point = self.initial_point

    def _initialize_state(self):
        """ Initialize the state of the sampler. """
        pass

    def _initialize_history(self):
        """ Allocate memory for the samples. """
        self._samples = []

    def _validate_initialization(self):
        """ Validate the initialization of the sampler. """

        for key in self._STATE_KEYS:
            if getattr(self, key) is None:
                raise ValueError(f"Sampler state key {key} is not set after initialization.")

        for key in self._HISTORY_KEYS:
            if getattr(self, key) is None:
                raise ValueError(f"Sampler history key {key} is not set after initialization.")
            
    @property
    def _default_initial_point(self):
        """ Return the default initial point for the sampler. Defaults to an array of ones. """
        return np.ones(self.dim)
    
    def __repr__(self):
        """ Return a string representation of the sampler. """
        if self.target is None:
            return f"Sampler: {self.__class__.__name__} \n Target: None"
        state = self.get_state()
        msg = f" Sampler: \n\t {self.__class__.__name__} \n Target: \n \t {self.target} \n Current state: \n"
        # Sort keys alphabetically
        keys = sorted(state['state'].keys())
        # Put _ in the end
        keys = [key for key in keys if key[0] != '_'] + [key for key in keys if key[0] == '_']
        for key in keys:
            value = state['state'][key]
            msg += f"\t {key}: {value} \n"
        return msg

class ProposalBasedSamplerNew(SamplerNew, ABC):
    """ Abstract base class for samplers that use a proposal distribution. """

    _STATE_KEYS = SamplerNew._STATE_KEYS.union({'current_target_logd', 'scale'})

    def __init__(self, target=None, proposal=None, scale=1, **kwargs):
        """ Initializer for proposal based samplers. 

        Parameters
        ----------
        target : cuqi.density.Density
            The target density.

        proposal : cuqi.distribution.Distribution, optional
            The proposal distribution. If not specified, the default proposal is used.

        scale : float, optional
            The scale parameter for the proposal distribution.

        **kwargs : dict
            Additional keyword arguments passed to the :class:`SamplerNew` initializer.

        """

        super().__init__(target, **kwargs)
        self.proposal = proposal
        self.initial_scale = scale
        self.current_target_logd = None # remove?
        self.scale = None # remove?

    def _set_defaults(self):
        super()._set_defaults()
        self.current_target_logd = self.target.logd(self.current_point)

    def _initialize_history(self):
        super()._initialize_history()
        self._acc = [ 1 ] # TODO. Check

    def _initialize_state(self):
        super()._initialize_state()
        self.scale = self.initial_scale

    @property
    def proposal(self):
        """ The proposal distribution. """
        if self._proposal is None:
            self._proposal = cuqi.distribution.Gaussian(np.zeros(self.dim), 1)
        return self._proposal
    
    @proposal.setter
    def proposal(self, proposal):
        """ Set the proposal distribution. """
        self._proposal = proposal


class _BatchHandler:
    """ Utility class to handle batching of samples. 
    
    If a batch size is specified, this class will save samples to disk in batches of the specified size.
     
    This is useful for very large sample sets that do not fit in memory.
     
    """
    
    def __init__(self, batch_size=0, sample_path='./CUQI_samples/'):

        if batch_size < 0:
            raise ValueError("Batch size should be a non-negative integer")

        self.sample_path = sample_path
        self._batch_size = batch_size
        self.current_batch = []
        self.num_batches_dumped = 0

    @property
    def sample_path(self):
        """ The path to save the samples. """
        return self._sample_path
    
    @sample_path.setter
    def sample_path(self, value):
        if not isinstance(value, str):
            raise TypeError("Sample path must be a string.")
        normalized_path = value.rstrip('/') + '/'
        if not os.path.isdir(normalized_path):
            try:
                os.makedirs(normalized_path, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Could not create directory at {normalized_path}: {e}")
        self._sample_path = normalized_path

    def add_sample(self, sample):
        """ Add a sample to the batch if batching. If the batch is full, flush the batch to disk. """

        if self._batch_size <= 0:
            return  # Batching not used

        self.current_batch.append(sample)

        if len(self.current_batch) >= self._batch_size:
            self.flush()

    def flush(self):
        """ Flush the current batch of samples to disk. """

        if not self.current_batch:
            return  # No samples to flush

        # Save the current batch of samples
        batch_samples = np.array(self.current_batch)
        file_path = f'{self.sample_path}batch_{self.num_batches_dumped:04d}.npz'
        np.savez(file_path, samples=batch_samples, batch_id=self.num_batches_dumped)

        self.num_batches_dumped += 1
        self.current_batch = []  # Clear the batch after saving

    def finalize(self):
        """ Finalize the batch handler. Flush any remaining samples to disk. """
        self.flush()
