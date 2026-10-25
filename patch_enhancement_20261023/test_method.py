import numpy as np,json
from generate import calculate,ROOT
rng=np.random.default_rng(2);v=np.exp(rng.normal(-4,0.3,(101,101)));h=v*.1;lee=10*np.log10(v);water=np.ones(v.shape,bool);px=(14,14)
x=calculate(v,h,lee,water,px);y=calculate(v*4,h*4,lee+10*np.log10(4),water,px)
assert np.allclose(x[:8],y[:8],equal_nan=True,atol=2e-5)
v=np.full((101,101),.01);h=v*.1;v[47:54,47:54]*=4;h[47:54,47:54]*=.25
x=calculate(v,h,10*np.log10(v),water,px);assert x[3,50,50]>0 and x[6,50,50]<0 and x[8,50,50]==7
v=np.full((101,101),.01);x=calculate(v,v*.1,10*np.log10(v),water,px);assert abs(x[3,50,50])<1e-5 and x[8,50,50]==0
(ROOT/'algorithm_checks.json').write_text(json.dumps({'multiplicative_backscatter_invariance':True,'opposite_signs_retained_in_agreement':True,'uniform_water_zero_contrast':True},indent=2));print('Checks passed')
