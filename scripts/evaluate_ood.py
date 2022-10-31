from collections import defaultdict

import transformers
from torch.utils.data import DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Trainer,
    TrainingArguments,
)
from datasets import load_metric
import torch
import numpy as np
import argparse

from typing import List, Dict, Any, Union, Optional, Tuple
from Todd import FilterType

from toddbenchmark.generation_data import prep_dataset, prep_model, prep_inputs
from toddbenchmark.utils import prepare_detectors, evaluate_dataloader

from configs.datasets_configs import DATASETS_CONFIGS


def parse_args():
    parser = argparse.ArgumentParser(description="Finetune a model on a dataset")
    parser.add_argument("--model_name", type=str, default="Helsinki-NLP/opus-mt-en-de")

    parser.add_argument("--in_config", type=str, default="wmt16_de_en")
    parser.add_argument(
        "--out_config", type=str, nargs="+", default="tatoeba_mt_deu_eng"
    )

    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--num_return_sequences", type=int, default=1)

    parser.add_argument("--max_length", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument(
        "--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu"
    )
    parser.add_argument("--output_dir", type=str, default="output")
    parser.add_argument("--output_file", type=str, default="output.txt")
    return parser.parse_args()


def load_requested_datasets(config_names: List[str], tokenizer):
    def tokenize_function(examples):
        return tokenizer(
            text=examples["source"], text_target=examples["target"], truncation=True
        )

    datasets = {}
    for config_name in config_names:
        if config_name not in DATASETS_CONFIGS:
            raise ValueError(
                f"Invalid dataset config name: {config_name}. "
                f"Available configs: {DATASETS_CONFIGS.keys()}"
            )
        config = DATASETS_CONFIGS[config_name]
        train_dataset, validation_dataset, test_dataset = prep_dataset(
            config["dataset_name"],
            config["dataset_config"],
            tokenizer,
        )

        validation_dataset = validation_dataset.map(
            tokenize_function,
            batched=True,
            num_proc=4,
        )

        test_dataset = test_dataset.map(
            tokenize_function,
            batched=True,
            num_proc=4,
        )

        validation_loader = torch.utils.data.DataLoader(
            validation_dataset,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=4,
        )


if __name__ == "__main__":
    args = parse_args()

    metrics = {
        "Accuracy": load_metric("accuracy"),
        "BLEU": load_metric("sacrebleu"),
        "rouge": load_metric("rouge"),
    }

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)

        return {
            k: m.compute(predictions=predictions, references=labels)
            for k, m in metrics.items()
        }

    model, tokenizer = prep_model(args.model_name)

    _, validation_dataset, test_dataset = prep_dataset(
        args.dataset_name, args.dataset_config, tokenizer
    )

    # Fit the detectors on the behavior of the model on the (in) validation set
    detectors = prepare_detectors(model, validation_dataset)

    test_loader = torch.utils.data.DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=4,
    )