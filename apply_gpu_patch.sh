#!/bin/bash
# Script để apply GPU patch cho xgboost_forecast.py
# Run: sudo bash apply_gpu_patch.sh

FILE="/home/hasu/actions-runner/_work/API_ETL_XGBoost/API_ETL_XGBoost/ml_pipeline/xgboost_forecast.py"

echo "Applying GPU patch to $FILE..."

# Backup
cp "$FILE" "$FILE.bak.$(date +%s)"

python3 << 'PYTHON'
import re

file_path = '/home/hasu/actions-runner/_work/API_ETL_XGBoost/API_ETL_XGBoost/ml_pipeline/xgboost_forecast.py'

with open(file_path, 'r') as f:
    content = f.read()

# Helper code
helper_code = '''\n\n# ============================================================================
# GPU SUPPORT HELPER FUNCTIONS
# ============================================================================\n\ndef get_xgboost_tree_method() -> str:
    """
    Xác định tree_method dựa trên environment variable USE_GPU.
    
    Returns:
        str: 'gpu_hist' nếu USE_GPU=true và GPU available, 'hist' nếu không
    """
    use_gpu = os.environ.get('USE_GPU', 'false').lower() == 'true'
    
    if use_gpu:
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("🎮 GPU detected via nvidia-smi, using tree_method='gpu_hist'")
                return 'gpu_hist'
            else:
                logger.warning("⚠️  USE_GPU=true but nvidia-smi failed, falling back to CPU (hist)")
                return 'hist'
        except Exception as e:
            logger.warning(f"⚠️  USE_GPU=true but GPU check failed: {e}, falling back to CPU (hist)")
            return 'hist'
    
    return 'hist'\n\n\ndef get_xgboost_device() -> str:
    """
    Xác định device cho XGBoost.
    
    Returns:
        str: 'cuda' nếu GPU available, 'cpu' nếu không
    """
    tree_method = get_xgboost_tree_method()
    return 'cuda' if tree_method == 'gpu_hist' else 'cpu'\n\n\n# Tạo alias để dễ dùng\nTREE_METHOD = get_xgboost_tree_method()\nDEVICE = get_xgboost_device()\n\nif TREE_METHOD == 'gpu_hist':\n    logger.info("🚀 XGBoost GPU mode enabled (gpu_hist)")\nelse:\n    logger.info("🖥️  XGBoost CPU mode (hist)")\n'''

# Thêm helper sau logger definition
pattern = r'(logger = logging\.getLogger\(__name__\))'
content = re.sub(pattern, r'\1' + helper_code, content)

# Thay thế tree_method
content = re.sub(r"tree_method='hist'", "tree_method=TREE_METHOD", content)
content = re.sub(r"'tree_method': 'hist'", "'tree_method': TREE_METHOD", content)

# Cập nhật comments
content = re.sub(r'# Fast histogram method cho CPU', '# Auto-detected: gpu_hist for GPU, hist for CPU', content)
content = re.sub(r'# Fast histogram \(CPU optimized\)', '# Auto-detected: gpu_hist for GPU, hist for CPU', content)

with open(file_path, 'w') as f:
    f.write(content)

print(f"✅ Patched: {file_path}")
PYTHON

# Verify
python3 -m py_compile "$FILE" && echo "✅ Syntax OK" || echo "❌ Syntax error"

echo "Done!"
