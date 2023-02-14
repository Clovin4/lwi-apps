import pandas as pd
import numpy as np
from pathlib import Path

def change_structure_name(geometry):
    
    geo=Path.read_text(geometry)
    return geometry