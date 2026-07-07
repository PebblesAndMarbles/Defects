HTML Defect Report Generator — Session Summary
Built two Python HTML report generators for semiconductor wafer defect imaging data. Report 1 (iGPT_ADHOC): single chamber/event token, images + wafermap + coord table in a fixed viewport three-panel layout. Report 2 (iGPT_ELEMENT_REPORT): filters EDX manifest by element symbol (e.g. "F"), 7-day lookback, all chambers, superimposed SVG wafermap (replaced matplotlib due to NumPy DLL/OOM errors), per-chamber colour coding. Key bugs fixed: target_date mtime filter dropping valid files; WAFER_ID composite-key mismatch resolved via FILE_WAFER extracted from LOCAL_IMAGE_FILE filename; manifest 4x row duplication fixed via drop_duplicates; coords CSV OOM fixed by replacing pandas read_csv with pure-Python line streaming.


