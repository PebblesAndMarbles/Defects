import pandas as pd

manifest = pd.read_csv('rollups/OTHER_UNKNOWN/8M5CL_RESULTS_CORRECTED/OTHER_UNKNOWN_IMAGES_MANIFEST.csv')

print("Sample LOCAL_IMAGE_FILE and transformed paths:")
for i, local_file in enumerate(manifest['LOCAL_IMAGE_FILE'].head(5)):
    rel_path = local_file.replace('\\', '/')
    if rel_path.startswith('rollups/OTHER_UNKNOWN/'):
        rel_path = '../' + rel_path[len('rollups/OTHER_UNKNOWN/'):]
    print(f"  {i}: {local_file}")
    print(f"     -> {rel_path}")
    print()
