"""Offline retrieval of Vaesen catalog topics using multilingual E5 embeddings."""

from pathlib import Path
import sys


MODEL_DIR = Path(__file__).resolve().parent / "build" / "semantic"


class SemanticCatalog:
    def __init__(self, catalog, directory=MODEL_DIR):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"), pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(directory / "model_quantized.onnx"), options,
                                            providers=["CPUExecutionProvider"])
        self.inputs = [item.name for item in self.session.get_inputs()]
        self.titles = [topic["title"] for topic in catalog]
        passages = ["passage: " + ". ".join([topic["title"], topic.get("summary") or "", *topic["aliases"]])
                    for topic in catalog]
        self.vectors = np.concatenate([self.encode(passages[start:start + 24]) for start in range(0, len(passages), 24)])
        examples = [(index, "query: " + example) for index, topic in enumerate(catalog)
                    for example in topic.get("voiceExamples", ())]
        self.example_indices = np.asarray([index for index, _ in examples], dtype=np.int64)
        self.example_vectors = self.encode([example for _, example in examples]) if examples else None

    def encode(self, texts):
        tokens = self.tokenizer.encode_batch(texts)
        np = self.np
        mask = np.asarray([token.attention_mask for token in tokens], dtype=np.int64)
        fields = {"input_ids": [token.ids for token in tokens], "attention_mask": mask,
                  "token_type_ids": [token.type_ids for token in tokens]}
        inputs = {name: np.asarray(fields[name], dtype=np.int64) for name in self.inputs}
        hidden = self.session.run(["last_hidden_state"], inputs)[0]
        vectors = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1, keepdims=True)
        return (vectors / np.linalg.norm(vectors, axis=1, keepdims=True)).astype(np.float32)

    def rank(self, text, limit=2):
        vector = self.encode(["query: " + text])[0]
        scores = self.vectors @ vector
        if self.example_vectors is not None:
            self.np.maximum.at(scores, self.example_indices, self.example_vectors @ vector - 0.012)
        return [(self.titles[index], float(scores[index])) for index in self.np.argsort(scores)[-limit:][::-1]]

    def lookup(self, text):
        ranked = self.rank(text.rstrip().rstrip(".!?") + "?")
        title, score = ranked[0]
        margin = score - ranked[1][1] if len(ranked) > 1 else score
        return title if score >= 0.875 and margin >= 0.008 else None


def load_semantic_catalog(catalog):
    if not (MODEL_DIR / "model_quantized.onnx").is_file() or not (MODEL_DIR / "tokenizer.json").is_file():
        return None
    dependencies = str(MODEL_DIR / "deps")
    if dependencies not in sys.path:
        sys.path.insert(0, dependencies)
    return SemanticCatalog(catalog)
