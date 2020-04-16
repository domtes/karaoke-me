'''
Pre-fetches the required model from github.
'''

import os
from spleeter.model.provider import get_default_model_provider


PREFETCH_MODELS = ['2stems']

for model_name in PREFETCH_MODELS:
    get_default_model_provider().download(
        model_name,
        os.path.join(os.getenv('MODEL_PATH'), model_name))
