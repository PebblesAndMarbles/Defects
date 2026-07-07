Session Summary — EDX Spectrum .emsa File Access
Objective: Retrieve raw EDX spectrum data (keV positions + peak areas) beyond what UDB.INSP_ELEMENT provides via the existing surf_scan_coordinates.py pipeline.
Investigation Path:
Traced EDX data flow through surf_scan_update.py → surf_scan_coordinates.py → confirmed SELECT e.* from INSP_ELEMENT only returns pre-pivoted EDX_ELEM{N}_{ELEMENT} weight-percent columns — no raw keV/counts data exists in the database.
Examined surf_scan_images.py — identified that SecureFTP.FtpFiles (from Intel.FabAuto.Quarc.Utilities.dll via pythonnet/clr) is the only available FTP method (no directory listing).
Queried UDB.INSP_WAFER_IMAGE with full primary key (WAFER_KEY, INSPECTION_TIME, DEFECT_ID) — critical to include INSPECTION_TIME to avoid full table scan timeout.
Discovered that IMAGE_IDs 13 and 14 return .emsa files (not .jpg), following the naming convention:
D1D-{TOOL}-{MMDDYY}@{HHMMSS}-{IDX}-{DEFECT_ID_PADDED}I{IMAGE_ID}K{KEY}.emsa
stored at FTP path /yas/data/images20/{server}/{date}/{hour}/{time}_{waferkey}/.
Next Step: Run fetch_spectrum_txt.py --wafer-key 7046563 --defect-id 3 with SPECTRUM_IMAGE_IDS = [13, 14, 15] and updated _build_txt_candidates() to download and preview the .emsa file, then integrate parsed keV/counts data into the pipeline.