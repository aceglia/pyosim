
from pathlib import Path

# path
PROJECT_PATH = Path('results')
CONF_TEMPLATE = Path('_conf.csv')

LOCAL_DATA_PARENT_PATH = Path('/home/laboratoire/mnt/F/Data/Shoulder/RAW')
DATA_PARENT_PATH = Path('/home/ubuntu/data/RAW')

LOCAL_MVC_PARENT_PATH = Path('/home/laboratoire/mnt/E/Projet_MVC/data/C3D_original_files/irsst_hf')
MVC_PARENT_PATH = Path('/home/ubuntu/data/mvc')

CALIBRATION_MATRIX = Path('../tests/data/forces_calibration_matrix.csv')

WU_MASS_FACTOR = 24.385 / 68.2
MODELS_PATH = PROJECT_PATH / '_models'
TEMPLATES_PATH = PROJECT_PATH / '_templates'
