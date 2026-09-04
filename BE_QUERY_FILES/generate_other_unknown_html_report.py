#!/usr/bin/env python3
"""
Generate a minimal HTML report for OTHER_UNKNOWN defect images.
- Just image tiles: brightfield on top, darkfield below
- No metadata, no cards - the burn-in has all the context needed
- Simple, efficient CSS Grid layout with responsive wrapping
"""

import pandas as pd
import os

def load_and_organize_images(layer_results_dir):
    """Load manifest and organize images by defect."""
    manifest_path = os.path.join(layer_results_dir, 'OTHER_UNKNOWN_IMAGES_MANIFEST.csv')
    if not os.path.exists(manifest_path):
        print(f"  WARNING: Manifest not found at {manifest_path}")
        return {}
    
    manifest = pd.read_csv(manifest_path)
    
    # Group by (LOT7, WAFER_ID, DEFECT_ID) to pair brightfield and darkfield
    defect_pairs = {}
    
    for _, row in manifest.iterrows():
        local_file = row.get('LOCAL_IMAGE_FILE', '')
        if not local_file or not isinstance(local_file, str) or local_file.strip() == '':
            continue
        
        # Skip if file doesn't exist
        if not os.path.isfile(local_file):
            continue
        
        # Extract image_id (2=brightfield, 3=darkfield)
        image_id = row.get('IMAGE_ID', '?')
        
        try:
            image_id_int = int(float(image_id))
        except:
            continue
        
        # Create a unique key for the defect pair
        lot7 = row.get('LOT7', 'UNK')
        wafer_id = row.get('WAFER_ID', 'UNK')
        defect_id = row.get('DEFECT_ID', 'UNK')
        
        key = (lot7, wafer_id, defect_id)
        if key not in defect_pairs:
            defect_pairs[key] = {}
        
        # Use relative path from HTML file location
        # HTML is at: rollups/OTHER_UNKNOWN/OTHER_UNKNOWN_IMAGES_TILES.html
        # Images are at: rollups/OTHER_UNKNOWN/8M5CL_RESULTS_CORRECTED/images/... or 8M6CL_RESULTS_CORRECTED/...
        # So relative paths are: 8M5CL_RESULTS_CORRECTED/images/... or 8M6CL_RESULTS_CORRECTED/images/...
        rel_path = local_file.replace('\\', '/')
        # Remove the rollups/OTHER_UNKNOWN/ prefix since HTML is in that folder
        if rel_path.startswith('rollups/OTHER_UNKNOWN/'):
            rel_path = rel_path[len('rollups/OTHER_UNKNOWN/'):]
        
        defect_pairs[key][image_id_int] = rel_path
    
    return defect_pairs

def generate_html(output_file='rollups/OTHER_UNKNOWN/OTHER_UNKNOWN_IMAGES_TILES.html'):
    """Generate minimal HTML with just image tiles."""
    
    print("Loading image manifests...")
    pairs_8m5 = load_and_organize_images('rollups/OTHER_UNKNOWN/8M5CL_RESULTS_CORRECTED')
    pairs_8m6 = load_and_organize_images('rollups/OTHER_UNKNOWN/8M6CL_RESULTS_CORRECTED')
    
    print(f"  8M5CL: {len(pairs_8m5)} defect pair(s)")
    print(f"  8M6CL: {len(pairs_8m6)} defect pair(s)")
    
    # HTML template
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OTHER_UNKNOWN Defects</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: #0d1117;
      padding: 16px;
      line-height: 1.6;
    }
    h1 { color: #c9d1d9; font-size: 24px; margin-bottom: 20px; }
    h2 { color: #79c0ff; font-size: 16px; margin: 30px 0 15px 0; padding-bottom: 8px; border-bottom: 1px solid #30363d; }
    
    /* Image tiles grid */
    .tiles-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(98px, 1fr));
      gap: 2px;
      margin-bottom: 30px;
    }
    
    /* Single tile: two images stacked (brightfield on top) */
    .tile {
      display: flex;
      flex-direction: column;
      gap: 0;
      background-color: #161b22;
      border: 1px solid #21262d;
    }
    
    .tile img {
      width: 100%;
      aspect-ratio: 1;
      object-fit: cover;
      display: block;
      border-bottom: 1px solid #21262d;
    }
    
    .tile img:last-child {
      border-bottom: none;
    }
    
    .tile img:hover {
      opacity: 0.85;
      cursor: zoom-in;
    }
  </style>
</head>
<body>
  <h1>OTHER_UNKNOWN Defects (234 images)</h1>
"""
    
    # Add 8M5CL tiles
    if pairs_8m5:
        html += f"  <h2>8M5CL — {len(pairs_8m5)} defects</h2>\n"
        html += "  <div class=\"tiles-grid\">\n"
        for key in sorted(pairs_8m5.keys()):
            images = pairs_8m5[key]
            img_2 = images.get(2)  # brightfield
            img_3 = images.get(3)  # darkfield
            
            if img_2 or img_3:
                html += "    <div class=\"tile\">\n"
                if img_2:
                    html += f"      <img src=\"{img_2}\" alt=\"brightfield\">\n"
                if img_3:
                    html += f"      <img src=\"{img_3}\" alt=\"darkfield\">\n"
                html += "    </div>\n"
        html += "  </div>\n"
    
    # Add 8M6CL tiles
    if pairs_8m6:
        html += f"  <h2>8M6CL — {len(pairs_8m6)} defects</h2>\n"
        html += "  <div class=\"tiles-grid\">\n"
        for key in sorted(pairs_8m6.keys()):
            images = pairs_8m6[key]
            img_2 = images.get(2)  # brightfield
            img_3 = images.get(3)  # darkfield
            
            if img_2 or img_3:
                html += "    <div class=\"tile\">\n"
                if img_2:
                    html += f"      <img src=\"{img_2}\" alt=\"brightfield\">\n"
                if img_3:
                    html += f"      <img src=\"{img_3}\" alt=\"darkfield\">\n"
                html += "    </div>\n"
        html += "  </div>\n"
    
    # Lightbox script
    html += """  <script>
    document.querySelectorAll(".tile img").forEach(img => {
      img.addEventListener("click", function() {
        const modal = document.createElement("div");
        modal.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.95);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:pointer;";
        const fullImg = document.createElement("img");
        fullImg.src = this.src;
        fullImg.style.cssText = "max-width:90vw;max-height:90vh;object-fit:contain;";
        modal.appendChild(fullImg);
        modal.addEventListener("click", () => modal.remove());
        document.body.appendChild(modal);
      });
    });
  </script>
</body>
</html>
"""
    
    # Write HTML
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\nHTML report generated: {output_file}")

if __name__ == '__main__':
    generate_html()

