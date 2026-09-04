#!/usr/bin/env python3
import pandas as pd

print('='*70)
print('FINAL RESULTS SUMMARY - OTHER_UNKNOWN DEFECT QUERY')
print('='*70)

# 8M5CL Results
coords_8m5 = pd.read_csv('rollups/OTHER_UNKNOWN/8M5CL_RESULTS_FINAL/OTHER_UNKNOWN_COORDINATES.csv')
manifest_8m5 = pd.read_csv('rollups/OTHER_UNKNOWN/8M5CL_RESULTS_FINAL/OTHER_UNKNOWN_IMAGES_MANIFEST.csv')

print()
print('8M5CL LAYER - Query from 34 wafers')
print('-' * 70)
print(f'  Defects found: {len(coords_8m5)}')
print(f'  Images downloaded: {len(manifest_8m5)}')
print(f'  Images successfully renamed: {manifest_8m5["LOCAL_IMAGE_FILE"].notna().sum()}')

# 8M6CL Results
coords_8m6 = pd.read_csv('rollups/OTHER_UNKNOWN/8M6CL_RESULTS_FINAL/OTHER_UNKNOWN_COORDINATES.csv')
manifest_8m6 = pd.read_csv('rollups/OTHER_UNKNOWN/8M6CL_RESULTS_FINAL/OTHER_UNKNOWN_IMAGES_MANIFEST.csv')

print()
print('8M6CL LAYER - Query from 46 wafers')
print('-' * 70)
print(f'  Defects found: {len(coords_8m6)}')
print(f'  Images downloaded: {len(manifest_8m6)}')
print(f'  Images successfully renamed: {manifest_8m6["LOCAL_IMAGE_FILE"].notna().sum()}')

print()
print('COMBINED TOTALS')
print('-' * 70)
total_defects = len(coords_8m5) + len(coords_8m6)
total_images = len(manifest_8m5) + len(manifest_8m6)
total_renamed = manifest_8m5["LOCAL_IMAGE_FILE"].notna().sum() + manifest_8m6["LOCAL_IMAGE_FILE"].notna().sum()
print(f'  Total defects: {total_defects}')
print(f'  Total images: {total_images}')
print(f'  Total images with valid paths: {total_renamed}')
print()
print('='*70)
