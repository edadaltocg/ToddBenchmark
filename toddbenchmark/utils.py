from collections import defaultdict
from typing import List, Dict

from torch.utils.data import DataLoader

from Todd import FilterType


def prepare_detectors(model, validation_dataset) -> List[FilterType]:
    return []


def evaluate_batch(
    model, data_loader: DataLoader, detectors: List[FilterType]
) -> Dict[str, float]:
    pass


def evaluate_dataloader(
    model,
    data_loader: DataLoader,
    tokenizer,
    detectors: List[FilterType],
    batch_size: int,
    num_beams: int,
    num_return_sequences: int,
    max_length: int,
) -> Dict[str, float]:
    records = defaultdict(list)

    for batch_idx, batch in enumerate(data_loader):
        x = batch["input_ids"]

        output = model.generate(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            max_length=max_length,
            num_beams=num_beams,
            num_return_sequences=num_return_sequences,
            early_stopping=True,
            return_dict_in_generate=True,
            output_scores=True,
            output_hidden_states=True,
        )

        # Should be a dictionary with keys ood scores,
        # each containing a numpy array of shape (batch_size, num_return_sequences))

        ood_scores = evaluate_batch(output, detectors)
        ood_scores = {
            k: scores.view(
                batch_size * num_return_sequences,
            ).tolist()
            for k, scores in ood_scores.items()
        }

        for k, scores in ood_scores.items():
            records[k].extend(scores)

        # A list of list ie each returned sequence for each batch
        decoded_sequences = tokenizer.batch_decode(
            output.sequences, skip_special_tokens=True
        )

    sequences_scores = output.sequences_scores.tolist()

    records["likelyhood"].extend(sequences_scores)