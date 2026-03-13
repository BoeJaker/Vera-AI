#!/usr/bin/env python3

import argparse
import os
import subprocess
import json
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling
)
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, PeftModel

############################################
# Utility
############################################

def run(cmd):
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


############################################
# Train LoRA
############################################

def train_lora(args):

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    dataset = load_dataset("json", data_files=args.dataset)

    def tokenize(example):
        return tokenizer(
            example["text"],
            truncation=True,
            padding="max_length",
            max_length=args.max_length
        )

    tokenized = dataset.map(tokenize)

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        device_map="auto"
    )

    config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=args.target_modules.split(","),
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM"
    )

    model = get_peft_model(model, config)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        num_train_epochs=args.epochs,
        logging_steps=10,
        save_strategy="epoch",
        fp16=True
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        data_collator=DataCollatorForLanguageModeling(
            tokenizer,
            mlm=False
        )
    )

    trainer.train()

    model.save_pretrained(os.path.join(args.output_dir, "lora_adapter"))


############################################
# Merge LoRA
############################################

def merge_lora(args):

    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        device_map="auto"
    )

    model = PeftModel.from_pretrained(
        base,
        os.path.join(args.output_dir, "lora_adapter")
    )

    merged = model.merge_and_unload()

    merged_dir = os.path.join(args.output_dir, "merged")

    merged.save_pretrained(merged_dir)

    return merged_dir


############################################
# Convert to GGUF
############################################

def convert_to_gguf(args, merged_dir):

    gguf = os.path.join(args.output_dir, "model.gguf")

    run([
        "python",
        f"{args.llama_cpp}/convert-hf-to-gguf.py",
        merged_dir,
        "--outfile",
        gguf
    ])

    return gguf


############################################
# Quantize
############################################

def quantize(args, gguf):

    quant = os.path.join(args.output_dir, f"model-{args.quant}.gguf")

    run([
        f"{args.llama_cpp}/quantize",
        gguf,
        quant,
        args.quant
    ])

    return quant


############################################
# Build Ollama model
############################################

def build_ollama(args, gguf):

    modelfile = os.path.join(args.output_dir, "Modelfile")

    with open(modelfile, "w") as f:
        f.write(f"""
FROM {gguf}

PARAMETER temperature {args.temperature}
PARAMETER top_p {args.top_p}

SYSTEM "{args.system_prompt}"
""")

    run([
        "ollama",
        "create",
        args.ollama_name,
        "-f",
        modelfile
    ])


############################################
# Main
############################################

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--base-model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", default="pipeline_output")

    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)

    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--target-modules", default="q_proj,v_proj")

    parser.add_argument("--max-length", type=int, default=2048)

    parser.add_argument("--llama-cpp", default="./llama.cpp")

    parser.add_argument("--quant", default="q4_K_M")

    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)

    parser.add_argument("--ollama-name", default="lora-model")
    parser.add_argument("--system-prompt", default="You are a helpful assistant.")

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    train_lora(args)

    merged_dir = merge_lora(args)

    gguf = convert_to_gguf(args, merged_dir)

    quant = quantize(args, gguf)

    build_ollama(args, quant)


if __name__ == "__main__":
    main()