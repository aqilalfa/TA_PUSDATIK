import sys
import logging
logging.basicConfig(level=logging.DEBUG)

sys.path.append('.')
from app.core.ingestion.document_manager import DocumentManager

mgr = DocumentManager()
print("Getting 12:", len(mgr.get_chunks("12")))
print("Getting 10:", len(mgr.get_chunks("10")))
