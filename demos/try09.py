# %%
import sys
sys.path.append("../")
import time
import numpy as np
import scipy as sp
import matplotlib.pyplot as plt
import scipy.sparse as sps

# myfuns
import cuqi

# %%
# Load cuqi deblur model and data
TP = cuqi.testproblem.Deblur()
model = TP.model #Deblur model
data = TP.data #Data from deblur problem
cov = TP.likelihood.cov
n = model.domain_geometry.dim
m = model.range_geometry.dim
x_true = TP.exactSolution

# %%
# Define Gaussian likelihood and prior
likelihood = cuqi.distribution.GaussianCov(model, cov)

var = 0.2
prior = cuqi.distribution.GaussianCov(0, var*np.ones(n))

# %% MAP estimates
# Define potential of posterior (returns logpdf and gradient w.r.t x)

def posterior_logpdf(x):
    logpdf = -prior.logpdf(x) - likelihood(x=x).logpdf(data) 
    return logpdf

def potential(x):
    logpdf = posterior_logpdf(x) 
    grad = -prior.gradient(x) - likelihood.gradient(data,x=x)
    return logpdf, grad

# Starting point
x0 = np.random.randn(n)

# Exact  MAP
prior2 = cuqi.distribution.Gaussian(np.zeros(n), np.sqrt(var), np.eye(n))
TP.prior = prior2
x_MAP_exact = TP.MAP()
print('relative error exact MAP:', np.linalg.norm(x_MAP_exact-x_true)/np.linalg.norm(x_true))

# L_BFGS_B MAP
solver = cuqi.solver.L_BFGS_B(potential, x0)
x_MAP_LBFGS = solver.solve()
print('relative error L-BFGS MAP:', np.linalg.norm(x_MAP_LBFGS-x_true)/np.linalg.norm(x_true))

# BFGS MAP
solver = cuqi.solver.minimize(posterior_logpdf, x0)
x_MAP_BFGS, info_MAP_BFGS = solver.solve()
print('relative error BFGS MAP:', np.linalg.norm(x_MAP_BFGS-x_true)/np.linalg.norm(x_true))

#%% SLSQP MAP
solver = cuqi.solver.minimize(posterior_logpdf, x0, method = 'SLSQP')
x_MAP_SLSQP, info_MAP_SLSQP = solver.solve()
print('relative error SLSQP MAP:', np.linalg.norm(x_MAP_SLSQP-x_true)/np.linalg.norm(x_true))


# %% plots
plt.plot(x_true, 'k-', label = "True")
plt.plot(x_MAP_exact, 'b-', label = "Exact MAP")
plt.plot(x_MAP_LBFGS, 'r--', label  = "LBFGS MAP")
plt.plot(x_MAP_BFGS, 'y:', label  = "BFGS MAP")
plt.plot(x_MAP_SLSQP, 'g:', label  = "SLSQP MAP")
plt.legend()
plt.show()

#%% ML estimates

def likelihood_logpdf(x):
    logpdf = - likelihood(x=x).logpdf(data) 
    return logpdf

def likelihood_potential(x):
    logpdf = likelihood_logpdf(x) 
    grad =  - likelihood.gradient(data,x=x)
    return logpdf, grad

# L_BFGS_B MAP
solver = cuqi.solver.L_BFGS_B(likelihood_potential, x0)
x_ML_LBFGS = solver.solve()
print('relative error L-BFGS ML:', np.linalg.norm(x_MAP_LBFGS-x_true)/np.linalg.norm(x_true))

# BFGS MAP
solver = cuqi.solver.minimize(likelihood_logpdf, x0)
x_ML_BFGS, info_ML_BFGS = solver.solve()
print('relative error BFGS ML:', np.linalg.norm(x_MAP_BFGS-x_true)/np.linalg.norm(x_true))

# %% plots
plt.plot(x_true, 'k-', label = "True")
#plt.plot(x_ML_exact, 'b-', label = "Exact ML")
plt.plot(x_ML_LBFGS, 'r--', label  = "LBFGS ML")
plt.plot(x_ML_BFGS, 'y:', label  = "BFGS ML")
plt.legend()
plt.show()

# %%

prob = cuqi.problem.BayesianProblem(likelihood, prior, data)
# %%
MAP_prob = prob.MAP()
# %%
print('relative error BFGS MAP:', np.linalg.norm(MAP_prob-x_true)/np.linalg.norm(x_true))
# %%
print('relative error BFGS MAP:', np.linalg.norm(MAP_prob-x_MAP_BFGS)/np.linalg.norm(x_MAP_BFGS))
# %%
