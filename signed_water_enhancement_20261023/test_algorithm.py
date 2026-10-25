import numpy as np,json
from enhance import derive,ring_sum,ROOT
w=[((11,11),(5,5)),((21,21),(9,9))];rng=np.random.default_rng(4);a=rng.normal(-17,2,(71,73));mask=np.ones(a.shape,bool)
x=derive(a,mask,w);shift=derive(a+8,mask,w);flipped=derive(-a,mask,w)
for band in [0,1,5,6]:
 assert np.allclose(x[band],shift[band],atol=2e-5,equal_nan=True)
 assert np.allclose(x[band],-flipped[band],atol=2e-5,equal_nan=True)
constant=derive(np.full(a.shape,-17.),mask,w);assert abs(constant[0,35,35])<1e-6
r,c=35,35;ring=a[r-5:r+6,c-5:c+6].copy();ring[3:8,3:8]=np.nan
assert np.isclose(x[2,r,c],np.nanmean(ring),atol=1e-5)
assert np.isclose(x[3,r,c],np.nanstd(ring),atol=1e-5)
mask[:,0:20]=False;b=a.copy();b[:,0:20]=10000
assert np.allclose(derive(a,mask,w)[:10],derive(b,mask,w)[:10],equal_nan=True)
# Bright and dark central perturbations preserve their signs and cannot enter guard-ring estimates.
a=np.full((71,73),-17.);a[35,35]=-11;a[35,55]=-23;x=derive(a,np.ones_like(a,bool),w)
assert x[0,35,35]>0 and x[0,35,55]<0
(ROOT/'algorithm_checks.json').write_text(json.dumps({'additive_db_invariance':True,'sign_reversal_symmetry':True,'constant_background_zero':True,'direct_annulus_mean_sd_match':True,'masked_land_ignored':True,'bright_and_dark_retained':True},indent=2))
print('Algorithm checks passed')
