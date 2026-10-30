import os
os.environ.pop('PROJ_LIB',None)
os.environ.pop('PROJ_DATA',None)
import sys,unittest
sys.path.insert(0,'D:/Masters/sar_server_pipeline/jobs/marida_16pec_20190116/qgis_deps')
sys.path.insert(0,'D:/Masters/Data_Creation/tests')
suite=unittest.defaultTestLoader.loadTestsFromName('test_build_global_s1_slc_inventory'); result=unittest.TextTestRunner(verbosity=1).run(suite);sys.exit(not result.wasSuccessful())

