from abc import ABC, abstractmethod

import numpy as np


class BaseFaceRecognizer(ABC):
    @abstractmethod
    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        raise NotImplementedError
