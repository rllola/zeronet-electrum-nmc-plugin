import os

eletrum_path = os.path.join(os.path.dirname(__file__),'Electrum-NMC')

# Install zip
if not os.path.exists(eletrum_path):
  import stat
  import zipfile

  eletrum_zip = os.path.join(os.path.dirname(__file__),'Electrum-NMC-3.3.10.zip')
  with zipfile.ZipFile(eletrum_zip,'r') as zip_ref:
    zip_ref.extractall(os.path.dirname(__file__))
  os.rename(os.path.join(os.path.dirname(__file__),'Electrum-NMC-3.3.10'), eletrum_path)
  electrum_executable = os.path.join(eletrum_path, 'run_electrum_nmc')
  st = os.stat(electrum_executable)
  os.chmod(electrum_executable, st.st_mode | stat.S_IEXEC)  

from . import UiRequestPlugin
from . import SiteManagerPlugin