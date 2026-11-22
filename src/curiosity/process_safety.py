"""Credential-free child processes for media and generated-code execution."""
from contextlib import contextmanager
import os
import subprocess

SAFE_NAMES={'PATH','HOME','LANG','TMPDIR','TMP','TEMP','SYSTEMROOT','LD_LIBRARY_PATH','VIRTUAL_ENV','PYTHONPATH','CURIOSITY_WORKDIR','XDG_CACHE_HOME','FONTCONFIG_PATH','FONTCONFIG_FILE'}
SAFE_PREFIXES=('LC_','OMP_','OPENBLAS_','MKL_')


def media_environment(source=None):
    source=os.environ if source is None else source
    return {key:value for key,value in source.items() if key in SAFE_NAMES or key.startswith(SAFE_PREFIXES)}


@contextmanager
def scrubbed_subprocesses():
    original_run,original_popen=subprocess.run,subprocess.Popen
    def run(*args,**kwargs):
        kwargs['env']=media_environment(kwargs.get('env'))
        return original_run(*args,**kwargs)
    def popen(*args,**kwargs):
        kwargs['env']=media_environment(kwargs.get('env'))
        return original_popen(*args,**kwargs)
    subprocess.run,subprocess.Popen=run,popen
    try:yield
    finally:subprocess.run,subprocess.Popen=original_run,original_popen
