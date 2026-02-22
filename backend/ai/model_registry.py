"""
Model Registry — QMS AI Module
Handles model versioning, saving, loading, and metadata.
"""
import os
import json
import joblib
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")
os.makedirs(MODEL_DIR, exist_ok=True)


class ModelRegistry:

    @staticmethod
    def save(factory_id: int, model_type: str, model, meta: dict) -> str:
        """Save model + metadata, return versioned path."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        model_name = f"{model_type}_factory{factory_id}_{ts}.pkl"
        meta_name  = f"{model_type}_factory{factory_id}_{ts}.meta.json"

        model_path = os.path.join(MODEL_DIR, model_name)
        meta_path  = os.path.join(MODEL_DIR, meta_name)

        joblib.dump(model, model_path, compress=3)
        with open(meta_path, "w") as f:
            json.dump({**meta, "model_path": model_path, "saved_at": ts}, f, indent=2)

        # Symlink latest
        latest_path = os.path.join(MODEL_DIR, f"{model_type}_factory{factory_id}_latest.pkl")
        latest_meta = os.path.join(MODEL_DIR, f"{model_type}_factory{factory_id}_latest.meta.json")

        for sym, target in [(latest_path, model_path), (latest_meta, meta_path)]:
            if os.path.islink(sym):
                os.unlink(sym)
            try:
                os.symlink(target, sym)
            except OSError:
                # Fallback: copy instead of symlink (Windows)
                import shutil
                shutil.copy2(target, sym)

        logger.info(f"[ModelRegistry] Saved {model_type} for factory {factory_id} → {model_path}")
        return model_path

    @staticmethod
    def load(factory_id: int, model_type: str) -> Tuple[Optional[object], Optional[dict]]:
        """Load latest model + metadata for factory."""
        model_path = os.path.join(MODEL_DIR, f"{model_type}_factory{factory_id}_latest.pkl")
        meta_path  = os.path.join(MODEL_DIR, f"{model_type}_factory{factory_id}_latest.meta.json")

        if not os.path.exists(model_path):
            return None, None

        try:
            model = joblib.load(model_path)
            meta  = {}
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
            return model, meta
        except Exception as e:
            logger.error(f"[ModelRegistry] Load failed: {e}")
            return None, None

    @staticmethod
    def exists(factory_id: int, model_type: str) -> bool:
        path = os.path.join(MODEL_DIR, f"{model_type}_factory{factory_id}_latest.pkl")
        return os.path.exists(path)

    @staticmethod
    def list_versions(factory_id: int, model_type: str) -> list:
        """List all saved versions for a factory model."""
        versions = []
        for fname in os.listdir(MODEL_DIR):
            if fname.startswith(f"{model_type}_factory{factory_id}_") and fname.endswith(".meta.json"):
                with open(os.path.join(MODEL_DIR, fname)) as f:
                    try:
                        versions.append(json.load(f))
                    except Exception:
                        pass
        return sorted(versions, key=lambda v: v.get("saved_at", ""), reverse=True)
