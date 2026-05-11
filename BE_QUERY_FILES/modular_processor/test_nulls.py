# test_nulls.py
from core.config import Config
from processors.defect_processor import DefectDataProcessor

config = Config()
processor = DefectDataProcessor(config)
df = processor.load_base_data()
df = processor.clean_and_rename_columns(df)
# ... other preprocessing steps ...

# Then call the debug method
trends_processor = processor.defect_trends_processor
trends_processor._debug_null_issue(df)