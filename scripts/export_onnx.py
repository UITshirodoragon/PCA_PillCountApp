from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_CHECKPOINTS = {
    "PANetNano": "./Networks/weights/model_best_nano.pth",
    "PANetBase": "./Networks/weights/model_best_base.pth",
    "PANet": "./Networks/weights/model_best_base.pth",
}
DEFAULT_EXPORT_ARCHES = ("PANetNano", "PANetBase")


def _load_state_dict(path: str) -> dict:
    ckpt = torch.load(path, map_location="cpu")
    if isinstance(ckpt, torch.nn.Module):
        return ckpt.state_dict()
    if not isinstance(ckpt, dict):
        raise ValueError(f"Unsupported checkpoint type: {type(ckpt)!r}")

    for key in ("state_dict", "model_state_dict", "net", "model"):
        value = ckpt.get(key)
        if isinstance(value, dict):
            return value

    if all(torch.is_tensor(v) for v in ckpt.values()):
        return ckpt
    raise ValueError("Unsupported checkpoint dict: cannot find state_dict")


def _strip_module_prefix(state: dict) -> dict:
    out = {}
    for key, value in state.items():
        new_key = key[7:] if isinstance(key, str) and key.startswith("module.") else key
        out[new_key] = value
    return out


def _require_module(module_name: str, package_name: str) -> None:
    if importlib.util.find_spec(module_name) is None:
        raise ImportError(f"Missing `{package_name}`. Install it with `pip install {package_name}` or `pip install -r requirements.txt`.")


def _first_output(output):
    if isinstance(output, (tuple, list)):
        return output[0]
    return output


def _export_one(args: argparse.Namespace, arch: str, checkpoint: str, output: str) -> None:
    from Networks import model_dict

    if arch not in model_dict:
        raise KeyError(f"Unknown arch {arch!r}; available: {list(model_dict.keys())}")

    model = model_dict[arch]().eval()
    state = _strip_module_prefix(_load_state_dict(checkpoint))
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        raise RuntimeError(f"Checkpoint does not match {arch}: missing={missing[:20]} unexpected={unexpected[:20]}")

    dummy = torch.zeros(1, 3, int(args.height), int(args.width), dtype=torch.float32)
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy,
            output,
            input_names=["input"],
            output_names=["density"],
            opset_version=int(args.opset),
            do_constant_folding=True,
        )

    print(f"Exported {arch}: {checkpoint} -> {output}")

    if args.check:
        import numpy as np
        import onnxruntime as ort

        with torch.no_grad():
            torch_out = _first_output(model(dummy)).detach().cpu().numpy()
        session = ort.InferenceSession(output, providers=["CPUExecutionProvider"])
        ort_out = session.run([session.get_outputs()[0].name], {session.get_inputs()[0].name: dummy.numpy()})[0]
        diff = float(np.max(np.abs(torch_out - ort_out)))
        print(f"ONNX check max_abs_diff={diff:.6f}")


def export_onnx(args: argparse.Namespace) -> None:
    os.chdir(ROOT)
    _require_module("onnx", "onnx")
    if args.check:
        _require_module("onnxruntime", "onnxruntime")

    if args.all:
        if args.checkpoint or args.output:
            raise ValueError("--all uses default checkpoint/output paths; omit --checkpoint and --output")
        for arch in DEFAULT_EXPORT_ARCHES:
            checkpoint = DEFAULT_CHECKPOINTS[arch]
            output = str(Path(checkpoint).with_suffix(".onnx"))
            _export_one(args, arch, checkpoint, output)
        return

    checkpoint = args.checkpoint or DEFAULT_CHECKPOINTS.get(args.arch)
    if not checkpoint:
        raise ValueError("--checkpoint is required for this architecture")
    output = args.output or str(Path(checkpoint).with_suffix(".onnx"))
    _export_one(args, args.arch, checkpoint, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a PillCounter PyTorch checkpoint to ONNX.")
    parser.add_argument("--arch", default="PANetNano", choices=["PANetNano", "PANetBase", "PANet"], help="Network architecture key.")
    parser.add_argument("--all", action="store_true", help="Export the default Nano and Base checkpoints.")
    parser.add_argument("--checkpoint", default="", help="Input .pth checkpoint. Defaults by --arch.")
    parser.add_argument("--output", default="", help="Output .onnx path. Defaults next to checkpoint.")
    parser.add_argument("--height", type=int, default=240, help="Model input height.")
    parser.add_argument("--width", type=int, default=320, help="Model input width.")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version.")
    parser.add_argument("--check", action="store_true", help="Compare PyTorch and ONNX outputs after export.")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        export_onnx(parse_args())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
