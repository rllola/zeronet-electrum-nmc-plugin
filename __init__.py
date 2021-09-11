import zipfile
import os

eletrum_path = os.path.join(os.path.dirname(__file__),'Electrum-NMC-3.3.10')

# Install zip
if not os.path.exists(eletrum_path):
  eletrum_zip = os.path.join(os.path.dirname(__file__),'Electrum-NMC-3.3.10.zip')
  with zipfile.ZipFile(eletrum_zip,'r') as zip_ref:
    zip_ref.extractall(os.path.join(eletrum_path)

from . import UiRequestPlugin
from . import SiteManagerPlugin
