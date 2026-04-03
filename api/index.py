import sys
from pathlib import Path

# أضف المجلد الرئيسي إلى مسار Python
sys.path.append(str(Path(__file__).parent.parent))

from app import app
