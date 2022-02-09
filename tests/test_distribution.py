from math import isnan
import cuqi
import numpy as np
import scipy as sp
import scipy.sparse as sps

from pytest import approx
import pytest

def test_Normal_mean_standard():
    assert cuqi.distribution.Normal(0,1).mean == approx(0.0)

def test_Normal_pdf_mean():
    pX = cuqi.distribution.Normal(0.1,1)
    assert pX.pdf(0.1) == approx(1.0/np.sqrt(2.0*np.pi))

@pytest.mark.parametrize("mean,var,expected",[
                            (2,3.5,[[8.17418321], [3.40055023]]),
                            (3.141592653589793,2.6457513110645907,[[7.80883646],[4.20030911]]),
                            (-1e-09, 1000000.0,[[1764052.34596766],[400157.20836722]]),
                            (1.7724538509055159, 0, [[1.77245385],[1.77245385]])
                        ])
def test_Normal_sample_regression(mean,var,expected):
    rng = np.random.RandomState(0) #Replaces legacy method: np.random.seed(0)
    samples = cuqi.distribution.Normal(mean,var).sample(2,rng=rng)
    target = np.array(expected).T
    assert np.allclose( samples.samples, target)

def test_Gaussian_mean():
    mean = np.array([0, 0])
    std = np.array([1, 1])
    R = np.array([[1, -0.7], [-0.7, 1]])
    pX_1 = cuqi.distribution.Gaussian(mean, std, R)
    assert np.allclose(pX_1.mean, np.array([0, 0]) ) 

def test_Gaussian_cov():
    mean = np.array([0, 0])
    std = np.array([1.3, 2])
    R = np.array([[1, -0.7], [-0.7, 1]])
    D = np.diag(std)
    S = D @ R @ D
    pX_1 = cuqi.distribution.Gaussian(mean, std, R)
    assert np.allclose(pX_1.Sigma, S) 

@pytest.mark.parametrize("mean,std,R,expected",[
                        (([0, 0]),
                        ([1, 1]),
                        ([[ 1. , -0.7],
                          [-0.7,  1. ]]),
                        ([[-1.47139568, -0.03445763, -2.10030149, -0.93455864,  0.2541872 ],
                          [ 1.78135612,  1.77024604,  1.3433053 ,  0.81731785,  0.06386104]])),

                        (([-3.14159265,  2.23606798]),
                        ([ 3.14159265, 50.        ]),
                        ([[ 1.   ,  0.001],
                          [-0.001,  1.   ]]),
                        ([[-1.88998123,  3.89532175, -6.21764722, -3.62006864, -1.85133578],
                          [90.43876395, 51.17340778, 95.61377534, 49.74045909, -2.92479388]])),

                        (([23.        ,  0.        ,  3.14159265]),
                        ([3.        , 1.41421356, 3.14159265]),
                        ([[ 1. ,  0.9,  0.3],
                          [0.9,  1. ,  0.5],
                          [-0.3, -0.5,  1. ]]),
                        ([[18.09724511, 16.68961957, 20.05485545, 22.20383097, 20.87158838],
                          [-2.79369395, -1.68366644, -1.31546803, -1.31802001, -1.24045592],
                          [ 0.85185965, -3.99395632,  3.10916299,  2.3865564 ,  2.31523876]]))
                        ])
def test_Gaussian_sample_regression(mean,std,R,expected):
    rng = np.random.RandomState(0)
    pX_1 = cuqi.distribution.Gaussian(np.array(mean), np.array(std), np.array(R))
    samples = pX_1.sample(5,rng=rng).samples
    assert np.allclose( samples, np.array(expected))

@pytest.mark.parametrize("seed",[3,4,5],ids=["seed3","seed4","seed5"])
@pytest.mark.parametrize("mean,var",[(2,3),(np.pi,0),(np.sqrt(5),1)]) 
def test_Normal_rng(mean,var,seed):
    np.random.seed(seed)
    rng = np.random.RandomState(seed)
    assert np.allclose(cuqi.distribution.Normal(mean,var).sample(10).samples,cuqi.distribution.Normal(mean,var).sample(10,rng=rng).samples)

@pytest.mark.parametrize("mean,std,R",[
                        (([0, 0]),
                        ([1, 1]),
                        ([[ 1. , -0.7],
                          [-0.7,  1. ]])),

                        (([-3.14159265,  2.23606798]),
                        ([ 3.14159265, 50.        ]),
                        ([[ 1.   ,  0.001],
                          [-0.001,  1.   ]])),
                        ])
def test_Gaussian_rng(mean,std,R):
    np.random.seed(3)
    rng = np.random.RandomState(3)
    assert np.allclose(cuqi.distribution.Gaussian(mean,std,R).sample(10).samples,cuqi.distribution.Gaussian(mean,std,R).sample(10,rng=rng).samples)

@pytest.mark.parametrize("dist",[cuqi.distribution.GMRF(np.ones(128),35,128,1,'zero'),cuqi.distribution.GMRF(np.ones(128),35,128,1,'periodic'),cuqi.distribution.GMRF(np.ones(128),35,128,1,'neumann')])
def test_GMRF_rng(dist):
    np.random.seed(3)
    rng = np.random.RandomState(3)
    assert np.allclose(dist.sample(10).samples,dist.sample(10,rng=rng).samples)

@pytest.mark.parametrize( \
  "low,high,toeval,expected",[ \
    (-2.0, 3.0, 1.0, np.log(0.2)), \
    (-2.0, 3.0, 3.5, -np.inf), \
    (np.array([1.0, 0.5]), np.array([2.0, 2.5]), np.array([1, 0.5]), np.log(0.5)), \
    (np.array([1.0, 0.5]), np.array([2.0, 2.5]), np.array([0.0, 0.5]), -np.inf), \
    (np.array([1.0, 0.5]), np.array([2.0, 2.5]), np.array([0.0, 0.0]), -np.inf), \
    (np.array([1.0, 0.5]), np.array([2.0, 2.5]), np.array([3.0, 0.5]), -np.inf), \
    (np.array([1.0, 0.5]), np.array([2.0, 2.5]), np.array([3.0, 3.0]), -np.inf), \
    (np.array([1.0, 2.0, 3.0]), np.array([3.0, 4.0, 5.0]), np.array([3.0, 4.0, 3.0]), np.log(0.125)), \
    (np.array([1.0, 2.0, 3.0]), np.array([3.0, 4.0, 5.0]), np.array([0.0, 5.0, 4.0]), -np.inf) \
  ])
def test_Uniform_logpdf(low, high, toeval, expected):
    UD = cuqi.distribution.Uniform(low, high)
    assert np.allclose(UD.logpdf(toeval), expected) 


@pytest.mark.parametrize("low,high,expected",[(np.array([1, .5]), 
                                               np.array([2, 2.5]),
                                               np.array([[1.5507979 , 1.29090474, 1.89294695],
                                               [1.91629565, 1.52165521, 2.29258618]])),
                                              (1,2,
                                               np.array([[1.5507979 , 1.70814782, 1.29090474]]))])
def test_Uniform_sample(low, high, expected):
    rng = np.random.RandomState(3)
    UD = cuqi.distribution.Uniform(low, high)
    cuqi_samples = UD.sample(3,rng=rng)
    print(cuqi_samples)
    assert np.allclose(cuqi_samples.samples, expected) 

@pytest.mark.parametrize("distribution, kwargs",
                         [(cuqi.distribution.Uniform, 
                          {'low':np.array([2, 2.5, 3,5]),
                          'high':np.array([5,7, 7,6])}),
                          (cuqi.distribution.Gaussian, 
                          {'mean':np.array([0, 0, 0, 0]),
                          'std':np.array([1, 1, 1, 1]),
                          'corrmat':np.eye(4)})])
def test_distribution_contains_geometry(distribution, kwargs):
    rng = np.random.RandomState(3)
    geom = cuqi.geometry.Continuous2D((2,2))
    dist = distribution(**kwargs,geometry = geom)
    cuqi_samples = dist.sample(3,rng=rng)
    assert(dist.dim == geom.dim and 
          cuqi_samples.geometry == geom and
          dist.geometry == geom and 
          np.all(geom.grid[0]==np.array([0, 1])) and
          np.all(geom.grid[1]== np.array([0, 1])))

# Compare computed covariance
@pytest.mark.parametrize("mean,cov,mean_full,cov_full",[
    ( (0),           (5),            (0),           (5)           ),
    ( (0),           (5*np.ones(3)), (np.zeros(3)), (5*np.eye(3)) ),
    ( (np.zeros(3)), (5),            (np.zeros(3)), (5*np.eye(3)) ),
    ( (np.zeros(3)), (5*np.ones(3)), (np.zeros(3)), (5*np.eye(3)) ),
    ( (0),           (5*np.eye(3)),  (np.zeros(3)), (5*np.eye(3)) ),
    ( (0),           (5*sps.eye(3)), (np.zeros(3)), (5*np.eye(3)) ),
    ( (0), (np.array([[5,3],[-3,2]])),       (np.zeros(2)), (np.array([[5,3],[-3,2]])) ),
    #( (0), (sps.csc_matrix([[5,3],[-3,2]])), (np.zeros(2)), (np.array([[5,3],[-3,2]])) ),
])
def test_GaussianCov(mean,cov,mean_full,cov_full):
    # Define cuqi dist using various means and covs
    prior = cuqi.distribution.GaussianCov(mean, cov)

    # Compare logpdf with scipy using full vector+matrix rep
    x0 = 1000*np.random.rand(prior.dim)
    eval1 = prior.logpdf(x0)
    eval2 = sp.stats.multivariate_normal.logpdf(x0, mean_full, cov_full)

    assert np.allclose(eval1,eval2)

    gradeval1 = prior.gradient(x0)
    gradeval2 = sp.optimize.approx_fprime(x0, prior.logpdf, 1e-15)

    assert np.allclose(gradeval1,gradeval2)

def test_InverseGamma_sample():
    a = [1,2]
    location = 0
    scale = 1
    N = 1000
    rng1 = np.random.RandomState(1)
    rng2 = np.random.RandomState(1)
    x = cuqi.distribution.InverseGamma(shape=a, location=location, scale=scale)
    samples1 = x.sample(N, rng=rng1).samples
    samples2 = sp.stats.invgamma.rvs(a=a, loc=location, scale=scale, size=(N,len(a)), random_state=rng2).T

    assert x.dim == len(a)
    assert np.all(np.isclose(samples1, samples2))

@pytest.mark.parametrize("a, location, scale",
                         [([1,2,1], [0,-1, 100], np.array([.1, 1, 20])),
                          (np.array([3,2,1]), (0, 0, 0), 1)])
@pytest.mark.parametrize("x",
                         [(np.array([1, 4, .5])),
                          (np.array([6, 6, 120])),
                          (np.array([1000, 0, -40]))])
@pytest.mark.parametrize("func", [("pdf"),("cdf"),("logpdf"),("gradient")])                        
def test_InverseGamma(a, location, scale, x, func):
    IGD = cuqi.distribution.InverseGamma(a, location=location, scale=scale)

    # PDF formula for InverseGamma
    def my_pdf( x, a, location, scale):
        if np.any(x <= location):
            val = x*0
        else:
            val =  (scale**a)\
            /((x-location)**(a+1)*sp.special.gamma(a))\
            *np.exp(-scale/(x-location))
        return val

    if func == "pdf":
        # The joint PDF of independent random vairables is the product of their individual PDFs.
        print("#########")
        print(IGD.pdf(x))
        print(np.prod(my_pdf(x, IGD.shape, IGD.location, IGD.scale)))

        assert np.all(np.isclose(IGD.pdf(x),np.prod(sp.stats.invgamma.pdf(x, a=a, loc=location, scale=scale)))) and np.all(np.isclose(IGD.pdf(x),np.prod(my_pdf(x, IGD.shape, IGD.location, IGD.scale))))

    elif func == "cdf":
        # The joint CDF of independent random vairables is the product of their individual CDFs.
        assert np.all(np.isclose(IGD.cdf(x),np.prod(sp.stats.invgamma.cdf(x, a=a, loc=location, scale=scale))))

    elif func == "logpdf":
        # The joint PDF of independent random vairables is the product of their individual PDFs (the product is replaced by sum for logpdf).
        assert np.all(np.isclose(IGD.logpdf(x),np.sum(sp.stats.invgamma.logpdf(x, a=a, loc=location, scale=scale)))) and np.all(np.isclose(IGD.logpdf(x),np.sum(np.log(my_pdf(x, IGD.shape, IGD.location, IGD.scale)))))

    elif func == "gradient":
        FD_gradient = cuqi.utilities.first_order_finite_difference_gradient(IGD.logpdf, x, IGD.dim, epsilon=0.000000001)
        #Assert that the InverseGamma gradient is close to the FD approximation or both gradients are nan.
        assert (np.all(np.isclose(IGD.gradient(x),FD_gradient,rtol=1e-3)) or
          (np.all(np.isnan(FD_gradient)) and np.all(np.isnan(IGD.gradient(x)))))

    else:
        raise ValueError
def test_lognormal_sample():
    rng = np.random.RandomState(3)
    mean = np.array([0, -4])
    std = np.array([1, 14])
    R = np.array([[1, -0.7], [-0.7, 1]])
    LND = cuqi.distribution.Lognormal(mean, std**2*R)
    cuqi_samples = LND.sample(3,rng=rng)
    result = np.array([[1.16127738e+00, 2.97702504e-01, 8.11608466e-01],
                       [1.89883185e+10, 8.10091757e-02, 2.50607929e-04]])
    assert(np.all(np.isclose(cuqi_samples.samples, result)))

@pytest.mark.parametrize("mean,std",[
                        (np.array([0, 0]),
                        np.array([1, 1])),
                        (np.array([-3.14159265,  2.23606798]),
                        np.array([3.14159265, 50.  ])),
                        (np.array([1.   ,  0.001]),
                        np.array([1, 120]))
                        ])
@pytest.mark.parametrize("x",[
                        (np.array([100, 0.00001])),
                        (np.array([0, -.45])),
                        (np.array([-3.14159265, 2.23606798]))])
def test_lognormal_logpdf(mean,std, x ):

    # CUQI lognormal x1,x2
    R = np.array([[1, 0], [0, 1]])
    LND = cuqi.distribution.Lognormal(mean, std**2*R)
    
    # Scipy lognormal for x1
    x_1_pdf_scipy = sp.stats.lognorm.pdf(x[0], s = std[0], scale= np.exp(mean[0]))

    # Scipy lognormal for x2
    x_2_pdf_scipy = sp.stats.lognorm.pdf(x[1], s = std[1], scale= np.exp(mean[1]))
    
    # x1 and x2 are independent 
    assert(np.isclose(LND.pdf(x), x_1_pdf_scipy*x_2_pdf_scipy))
    assert(np.isclose(LND.logpdf(x), np.log(x_1_pdf_scipy*x_2_pdf_scipy)))

@pytest.mark.parametrize("mean, std, R",[
                        (np.array([0, 0]),
                        np.array([1, 1]),
                        np.array([[1, .3], [.3, 1]])),
                        (np.array([-3.14159265,  2.23606798]),
                        np.array([3.14159265, 50.  ]),
                        np.array([[1, 0], [0, 1]])),
                        (np.array([1.   ,  0.001]),
                        np.array([1, 120]),
                        np.array([[2, 2], [2, 14]]))
                        ])
@pytest.mark.parametrize("val",[
                        (np.array([100, 0.1])),
                        (np.array([-10, .1])),
                        (np.array([0.1, .45])),
                        (np.array([3.14159265, 2.23606798]))])
def test_gradient_lognormal_as_prior(mean, std, R, val):
    # This test verifies the lognormal distribution gradient correctness
    # (when the mean is a numpy.ndarray) by comparing it with a finite
    # difference approximation of the gradient.

    # ------------------- 1. Create lognormal distribution --------------------
    LND = cuqi.distribution.Lognormal(mean, std**2*R)
    
    # -------------- 2. Create the finite difference gradient -----------------
    eps = 0.000001
    FD_gradient = np.empty(LND.dim)
    
    for i in range(LND.dim):
        # compute the ith component of the gradient
        eps_vec = np.zeros(LND.dim)
        eps_vec[i] = eps
        val_plus_eps = val + eps_vec
        FD_gradient[i] = (LND.logpdf(val_plus_eps) - LND.logpdf(val))/eps 

    # ---------------- 3. Verify correctness of the gradient ------------------
    assert(np.all(np.isclose(FD_gradient, LND.gradient(val))) or
           (np.all(np.isnan(FD_gradient)) and np.all(np.isnan(LND.gradient(val))) )
           )

@pytest.mark.parametrize("std, R",[
                        (
                        3,
                        np.array([[1, .3, 0], [.3, 1, .3], [0, .3, 1]])),
                        (
                        12,
                        np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]))
                        ])
@pytest.mark.parametrize("val",[
                        (np.array([10, 0.1, 3])),
                        (np.array([0.1, .45, 6]))])
@pytest.mark.parametrize("x",[
                        (np.array([1, -0.1])),
                        (np.array([-3.14159265, 2.23606798]))])
                      
def test_gradient_lognormal_as_likelihood(std, R, val, x):
    # This test verifies the lognormal distribution gradient correctness
    # (when the mean is a cuqi.Model) by comparing it with a finite
    # difference approximation of the gradient.

    # ------------------------ 1. Create a cuqi.model -------------------------
    domain_geometry = 2
    range_geometry = 3

    # model's forward function
    def forward(x=None):
        return np.array([np.exp(x[0]) + x[1],
             np.exp(2*x[1]) + 3*x[0],
             x[0]+2*x[1]])
    
    # model's gradient
    def gradient(val, x=None):
        jac = np.zeros((range_geometry, domain_geometry))
        jac[0,0] =  np.exp(x[0])#d f1/ d x1
        jac[0,1] =  1 #d f1/ d x2
    
        jac[1,0] =  3 #d f2/ d x1
        jac[1,1] =  2*np.exp(2*x[1]) #d f2/ d x2
    
        jac[2,0] =  1 #d f2/ d x1
        jac[2,1] =  2 #d f2/ d x2
    
        return jac.T@val
    
    # create the cuqi.Model
    model = cuqi.model.Model(forward=forward, 
                             domain_geometry=domain_geometry, 
    			 range_geometry=range_geometry)
    model.gradient = gradient
    
    # ------------------- 2. Create lognormal distribution --------------------
    LND = cuqi.distribution.Lognormal(model, std**2*R)
    
    # -------------- 3. Create the finite difference gradient -----------------
    eps = 0.000001
    FD_gradient = np.empty(domain_geometry)
 
    for i in range(domain_geometry):
        eps_vec = np.zeros(domain_geometry)
        eps_vec[i] = eps
        x_plus_eps = x + eps_vec
        FD_gradient[i] = (LND(x=x_plus_eps).logpdf(val) - LND(x=x).logpdf(val))/eps
    
    # ---------------- 4. Verify correctness of the gradient ------------------
    assert(np.all(np.isclose(FD_gradient, LND.gradient(val, x=x))))

def test_beta(): #TODO. Make more tests
    alpha = 2; beta = 5; x=0.5

    # Create beta distribution
    BD = cuqi.distribution.Beta(alpha, beta)

    # Gamma function
    gamma = lambda x: sp.special.gamma(x)

    # Direct PDF formula for Beta
    def my_pdf( x, a, b):
        if np.any(x<=0) or np.any(x>=1) or np.any(a<=0) or np.any(b<=0):
            val = x*0
        else:
            val = gamma(a+b)/(gamma(a)*gamma(b)) * x**(a-1) * (1-x)**(b-1)
        return val

    # PDF
    assert np.allclose(BD.pdf(x), my_pdf(x, BD.alpha, BD.beta))

    # CDF
    assert np.allclose(BD.cdf(x),np.prod(sp.stats.beta.cdf(x, a=alpha, b=beta)))

    # logpdf
    assert np.allclose(BD.logpdf(x), np.log(my_pdf(x, alpha, beta)))
    
    # GRADIENT
    FD_gradient = cuqi.utilities.first_order_finite_difference_gradient(BD.logpdf, x, BD.dim, epsilon=0.000000001)
    assert np.allclose(BD.gradient(x),FD_gradient,rtol=1e-3) or (np.all(np.isnan(FD_gradient)) and np.all(np.isnan(BD.gradient(x))))
