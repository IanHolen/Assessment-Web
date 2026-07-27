#!/usr/bin/env python3
"""
Inferencia local del modelo de recomendación de cultivos (numpy puro, sin PyTorch).

Reemplaza al GPUInferenceClient original (que llamaba a un servicio GPU remoto).
El modelo es un MLP pequeño (7 -> 64 -> 64 -> 22) entrenado en PyTorch; aquí se
ejecuta el forward pass con numpy usando los pesos exportados a .npz.

Expone la MISMA interfaz que esperaba el backend:
  engine.predict(features) / health_check() / get_crops() / get_features()
  engine.label_mapping / engine.feature_names / engine.feature_ranges / engine.models
"""
import os
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))

# Orden de features que espera el modelo (igual que el StandardScaler y el dataset).
FEATURE_ORDER = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

# Rangos agronómicos aproximados (dataset Crop_recommendation) para el endpoint /features.
FEATURE_RANGES = {
    "N": (0, 140), "P": (5, 145), "K": (5, 205),
    "temperature": (8.0, 44.0), "humidity": (14.0, 100.0),
    "ph": (3.5, 10.0), "rainfall": (20.0, 300.0),
}


class LocalInferenceClient:
    """Cliente de inferencia en proceso (drop-in del antiguo GPUInferenceClient)."""

    def __init__(self, model_dir: str = _DIR):
        w = np.load(os.path.join(model_dir, "model_weights.npz"))
        self.W0, self.b0 = w["encoder.0.weight"], w["encoder.0.bias"]  # (64,7)
        self.W2, self.b2 = w["encoder.2.weight"], w["encoder.2.bias"]  # (64,64)
        self.W4, self.b4 = w["encoder.4.weight"], w["encoder.4.bias"]  # (22,64)

        s = np.load(os.path.join(model_dir, "scaler.npz"))
        self.mean, self.scale = s["mean"], s["scale"]

        with open(os.path.join(model_dir, "label_mapping.json")) as f:
            self.label_mapping = json.load(f)          # crop -> idx
        self.inverse_label_mapping = {int(v): k for k, v in self.label_mapping.items()}

        self.feature_names = list(FEATURE_ORDER)
        self.feature_ranges = dict(FEATURE_RANGES)
        # Compatibilidad: el backend hace engine.models.keys() al arrancar.
        self.models = {"DropClassifier": "loaded"}
        logger.info("LocalInferenceClient listo (%d cultivos, numpy in-process)",
                    len(self.label_mapping))

    def _forward(self, x: np.ndarray) -> np.ndarray:
        """x: vector (7,) sin normalizar -> probabilidades (22,)."""
        xs = (x - self.mean) / self.scale
        h = np.maximum(0.0, self.W0 @ xs + self.b0)   # Linear + ReLU
        h = np.maximum(0.0, self.W2 @ h + self.b2)    # Linear + ReLU
        logits = self.W4 @ h + self.b4                # Linear
        z = logits - logits.max()
        e = np.exp(z)
        return e / e.sum()                            # softmax

    def health_check(self):
        return {"status": "healthy", "service": "local-inference", "model": "DropClassifier"}

    def predict(self, features: dict):
        try:
            x = np.array([float(features[k]) for k in FEATURE_ORDER], dtype=np.float64)
        except (KeyError, ValueError, TypeError) as e:
            return {"success": False, "error": f"Invalid features: {e}",
                    "predicted_crop": None, "confidence": 0.0}

        probs = self._forward(x)
        order = np.argsort(probs)[::-1]
        top = [{"crop": self.inverse_label_mapping[int(i)],
                "probability": round(float(probs[i]), 4)} for i in order[:3]]
        pred = int(order[0])
        return {
            "success": True,
            "predicted_crop": self.inverse_label_mapping[pred],
            "confidence": round(float(probs[pred]), 4),
            "top_predictions": top,
            "input_features": features,
            "warnings": None,
        }

    def get_crops(self):
        crops = sorted(self.label_mapping.keys())
        return {"crops": crops, "count": len(crops)}

    def get_features(self):
        return {"features": self.feature_names, "count": len(self.feature_names)}
