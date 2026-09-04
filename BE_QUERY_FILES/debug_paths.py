import pandas as pd
import os

manifest = pd.read_csv('rollups/OTHER_UNKNOWN/8M5CL_RESULTS_CORRECTED/OTHER_UNKNOWN_IMAGES_MANIFEST.csv')
print('Sample LOCAL_IMAGE_FILE paths (first 5):')
for i, path in enumerate(manifest['LOCAL_IMAGE_FILE'].head(5)):
    print(f'  {i}: {path}')
    
print()
print('Path characteristics:')
first_path = manifest['LOCAL_IMAGE_FILE'].iloc[0]
print(f'  Type: {type(first_path)}')
print(f'  Absolute path?: {":" in str(first_path)}')

# Check if first file actually exists
exists = os.path.isfile(first_path)
print(f'  First file exists: {exists}')
if exists:
    print(f'    File size: {os.path.getsize(first_path)} bytes')
    
# Get current working directory
print(f'\n  Current CWD: {os.getcwd()}')
print(f'  BE folder check: {os.path.isdir("rollups/OTHER_UNKNOWN/8M5CL_RESULTS_CORRECTED")}')
